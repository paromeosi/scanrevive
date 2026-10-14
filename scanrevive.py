#!/usr/bin/env python3
"""ScanRevive: a web interface that keeps old SANE scanners (made for the Canon LiDE 110) working on modern macOS.

It talks to libsane directly through ctypes, so the only requirement is SANE itself:
    brew install sane-backends
    python3 scanrevive.py            # then open http://localhost:8110
"""
import argparse
import array
import ctypes
import ctypes.util
import json
import mimetypes
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zlib
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
FORMATS = {"png": ".png", "jpeg": ".jpg", "tiff": ".tif", "pdf": ".pdf"}
EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf")
DEFAULTS = {"mode": "Color", "resolution": 300}  # friendlier than most backends' 75 dpi gray


# ---------------------------------------------------------------- libsane binding (SANE standard 1.0)

class Device(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("vendor", ctypes.c_char_p),
                ("model", ctypes.c_char_p), ("type", ctypes.c_char_p)]


class Range(ctypes.Structure):
    _fields_ = [("min", ctypes.c_int), ("max", ctypes.c_int), ("quant", ctypes.c_int)]


class Constraint(ctypes.Union):
    _fields_ = [("string_list", ctypes.POINTER(ctypes.c_char_p)),
                ("word_list", ctypes.POINTER(ctypes.c_int)),
                ("range", ctypes.POINTER(Range))]


class OptionDescriptor(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("title", ctypes.c_char_p), ("desc", ctypes.c_char_p),
                ("type", ctypes.c_int), ("unit", ctypes.c_int), ("size", ctypes.c_int), ("cap", ctypes.c_int),
                ("constraint_type", ctypes.c_int), ("constraint", Constraint)]


class Parameters(ctypes.Structure):
    _fields_ = [("format", ctypes.c_int), ("last_frame", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
                ("pixels_per_line", ctypes.c_int), ("lines", ctypes.c_int), ("depth", ctypes.c_int)]


BOOL, INT, FIXED, STRING, BUTTON, GROUP = range(6)
TYPES = ["bool", "int", "fixed", "string", "button", "group"]
UNITS = ["", "px", "bit", "mm", "dpi", "%", "µs"]
CAP_SOFT_SELECT, CAP_HARD_SELECT, CAP_INACTIVE, CAP_ADVANCED = 1, 2, 32, 64
GOOD, CANCELLED, EOF, IO_ERROR = 0, 2, 5, 9
GET, SET = 0, 1
FRAME_GRAY, FRAME_RGB = 0, 1
L = None  # libsane, loaded in main()


def load_libsane():
    candidates = [ctypes.util.find_library("sane"), "/opt/homebrew/lib/libsane.1.dylib",
                  "/usr/local/lib/libsane.1.dylib", "libsane.so.1"]
    for path in filter(None, candidates):
        try:
            lib = ctypes.CDLL(path)
            break
        except OSError:
            pass
    else:
        sys.exit("libsane not found. Install SANE first:  brew install sane-backends")
    P = ctypes.POINTER
    sigs = {
        "sane_init": (ctypes.c_int, [P(ctypes.c_int), ctypes.c_void_p]),
        "sane_exit": (None, []),
        "sane_get_devices": (ctypes.c_int, [P(P(P(Device))), ctypes.c_int]),
        "sane_open": (ctypes.c_int, [ctypes.c_char_p, P(ctypes.c_void_p)]),
        "sane_close": (None, [ctypes.c_void_p]),
        "sane_get_option_descriptor": (P(OptionDescriptor), [ctypes.c_void_p, ctypes.c_int]),
        "sane_control_option": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                               ctypes.c_void_p, P(ctypes.c_int)]),
        "sane_get_parameters": (ctypes.c_int, [ctypes.c_void_p, P(Parameters)]),
        "sane_start": (ctypes.c_int, [ctypes.c_void_p]),
        "sane_read": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, P(ctypes.c_int)]),
        "sane_cancel": (None, [ctypes.c_void_p]),
        "sane_strstatus": (ctypes.c_char_p, [ctypes.c_int]),
    }
    for name, (res, args) in sigs.items():
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = res, args
    return lib


class SaneError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(L.sane_strstatus(status).decode())


class Busy(Exception):
    pass


class Cancelled(Exception):
    pass


def check(status):
    if status != GOOD:
        raise SaneError(status)


def txt(b):
    return b.decode("utf-8", "replace") if b else ""


# ---------------------------------------------------------------- image output (stdlib PNG, sips for the rest)

INVERT = bytes(255 - i for i in range(256))


class PngWriter:
    """Streams scanner lines straight into a PNG file, so big scans never sit in memory."""

    def __init__(self, path, width, bytes_per_line, depth, channels, dpi):
        self.path, self.w, self.bpl, self.depth, self.ch = Path(path), width, bytes_per_line, depth, channels
        self.rowlen = (width * channels * depth + 7) // 8
        if depth not in (1, 8, 16) or (depth == 1 and channels != 1) or bytes_per_line < self.rowlen:
            raise RuntimeError(f"Unsupported image format ({channels} channel(s), {depth} bit)")
        self.rows, self.pending, self.z = 0, b"", zlib.compressobj(6)
        self.f = open(self.path, "wb")
        self.f.write(b"\x89PNG\r\n\x1a\n")
        self._ihdr()  # height is unknown until the end: rewritten in close()
        ppm = round(dpi / 0.0254)
        self._chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))

    def _chunk(self, tag, data):
        self.f.write(struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data)))

    def _ihdr(self):
        self._chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.rows, self.depth, 2 if self.ch == 3 else 0, 0, 0, 0))

    def write(self, data):
        data = self.pending + data
        cut = len(data) - len(data) % self.bpl
        self.pending = data[cut:]
        out = []
        for k in range(0, cut, self.bpl):
            row = data[k:k + self.rowlen]
            if self.depth == 1:
                row = row.translate(INVERT)  # SANE: 1 = black, PNG: 0 = black
            elif self.depth == 16 and sys.byteorder == "little":
                a = array.array("H", row)  # SANE sends host byte order, PNG wants big-endian
                a.byteswap()
                row = a.tobytes()
            out.append(b"\x00" + row)
        self.rows += cut // self.bpl
        packed = self.z.compress(b"".join(out))
        if packed:
            self._chunk(b"IDAT", packed)

    def close(self):
        if not self.rows:
            self.abort()
            raise RuntimeError("The scanner returned an empty image")
        self._chunk(b"IDAT", self.z.flush())
        self._chunk(b"IEND", b"")
        self.f.seek(8)
        self._ihdr()
        self.f.close()
        return self.w, self.rows

    def abort(self):
        self.f.close()
        self.path.unlink(missing_ok=True)


def run(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or f"{cmd[0]} failed")
    return r.stdout


def image_info(path):
    out = run("sips", "-g", "pixelWidth", "-g", "pixelHeight", "-g", "dpiWidth", "-g", "samplesPerPixel", path)
    v = dict(re.findall(r"(\w+): ([\d.]+)", out))
    return (int(v["pixelWidth"]), int(v["pixelHeight"]),
            float(v.get("dpiWidth", 0)) or 72.0, int(v.get("samplesPerPixel", 3)))


def make_pdf(images, out, quality=85):
    """Multi-page PDF, one JPEG per page at its real size (an A4 scan gives an A4 page)."""
    objs, kids = [b"", b""], []
    with tempfile.TemporaryDirectory() as tmp:
        for k, img in enumerate(images):
            jpg = img
            if img.suffix.lower() not in (".jpg", ".jpeg"):
                jpg = Path(tmp, f"{k}.jpg")
                run("sips", "-s", "format", "jpeg", "-s", "formatOptions", quality, img, "--out", jpg)
            w, h, dpi, spp = image_info(jpg)
            data = jpg.read_bytes()
            pw, ph = w * 72 / dpi, h * 72 / dpi
            space = {1: b"DeviceGray", 4: b"DeviceCMYK"}.get(spp, b"DeviceRGB")
            draw = b"q %.3f 0 0 %.3f 0 0 cm /Im Do Q" % (pw, ph)
            n = len(objs)
            objs.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s "
                        b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n%s\nendstream"
                        % (w, h, space, len(data), data))
            objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(draw), draw))
            objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] "
                        b"/Resources << /XObject << /Im %d 0 R >> >> /Contents %d 0 R >>" % (pw, ph, n + 1, n + 2))
            kids.append(b"%d 0 R" % (n + 3))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(kids), len(kids))
    pdf, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    Path(out).write_bytes(pdf)
    return Path(out)


def convert(png, fmt, quality):
    """PNG -> requested format. On failure the PNG is kept, so a scan is never lost."""
    if fmt == "png":
        return png
    out = png.with_suffix(FORMATS[fmt])
    try:
        if fmt == "pdf":
            make_pdf([png], out, quality)
        else:
            run("sips", "-s", "format", fmt, "-s", "formatOptions", quality if fmt == "jpeg" else "lzw", png, "--out", out)
    except (OSError, RuntimeError) as e:
        raise RuntimeError(f"Saved as {png.name}, but conversion to {fmt.upper()} failed: {e}")
    png.unlink()
    return out


def new_path(prefix, ext):
    stem = time.strftime(prefix + "-%Y%m%d-%H%M%S")
    name, k = stem, 1
    while any((OUT / (name + e)).exists() for e in EXTS):
        k += 1
        name = f"{stem}-{k}"
    return OUT / (name + ext)


def scan_path(name):
    """Resolve a file name from the browser to a file in the output folder, refusing anything else."""
    p = OUT / Path(name).name
    return p if p.name == name and not name.startswith(".") and p.suffix.lower() in EXTS and p.is_file() else None


def list_scans():
    files = [p for p in OUT.iterdir() if p.suffix.lower() in EXTS and not p.name.startswith(".")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size} for p in files]


def thumbnail(name):
    src = scan_path(name)
    if not src or not shutil.which("sips"):
        return None
    dst = OUT / ".thumbs" / (name + ".jpg")
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(exist_ok=True)
        try:
            run("sips", "-Z", "360", "-s", "format", "jpeg", src, "--out", dst)
        except RuntimeError:
            return None
    return dst


# ---------------------------------------------------------------- hardware buttons

def send_mail(path):
    run(*(["open", "-a", "Mail", path] if sys.platform == "darwin" else ["xdg-email", "--attach", path]))


def print_file(path):
    run("lp", "-o", "fit-to-page", path)


# name -> (format or None for "last used", follow-up action, description shown in the UI)
BUTTONS = {
    "scan": (None, None, "Scan with the current settings"),
    "file": ("pdf", None, "Scan to PDF"),
    "pdf": ("pdf", None, "Scan to PDF"),
    "email": ("jpeg", send_mail, "Scan and attach to a new email"),
    "copy": ("png", print_file, "Scan and print (photocopy)"),
}


# ---------------------------------------------------------------- the scanner

class Scanner:
    def __init__(self, want=""):
        self.lock = threading.Lock()
        self.h = None
        self.inited = False
        self.want = want  # matched against "name vendor model"; becomes "vendor model" once opened
        self.device, self.devices, self.error = None, [], None
        self.user_values = {}  # re-applied after a reconnect
        self.job = {"id": 0, "state": "idle"}
        self.events, self.event_id = [], 0
        self.preview = None
        self.last_format, self.last_quality = "png", 85
        self._cancel = False
        self._next_try = 0.0

    # --- device lifecycle

    @contextmanager
    def session(self):
        """Exclusive access to an open device. An I/O error closes it, so the next call reconnects."""
        if not self.lock.acquire(timeout=3):
            raise Busy("The scanner is busy")
        try:
            if self.h is None:
                self._open()
            yield
        except SaneError as e:
            if e.status == IO_ERROR:
                self._close()
            raise
        finally:
            self.lock.release()

    def _open(self):
        # Fresh USB enumeration every time: the LiDE 110 changes USB address after each close.
        if self.inited:
            L.sane_exit()
        check(L.sane_init(None, None))
        self.inited = True
        lst = ctypes.POINTER(ctypes.POINTER(Device))()
        check(L.sane_get_devices(ctypes.byref(lst), 0))
        devs, i = [], 0
        while lst[i]:
            d = lst[i].contents
            devs.append({k: txt(getattr(d, k)) for k in ("name", "vendor", "model", "type")})
            i += 1
        self.devices = devs
        if not devs:
            raise RuntimeError("No scanner found. Is it plugged in?")
        label = lambda d: f"{d['name']} {d['vendor']} {d['model']}".lower()
        dev = next((d for d in devs if self.want and self.want.lower() in label(d)), devs[0])
        h = ctypes.c_void_p()
        check(L.sane_open(dev["name"].encode(), ctypes.byref(h)))
        self.h, self.device, self.error = h, dev, None
        self.want = f"{dev['vendor']} {dev['model']}"
        for values in (DEFAULTS, dict(self.user_values)):
            for k, v in values.items():
                try:
                    self._set(k, v)
                except (SaneError, KeyError, ValueError):
                    pass

    def _close(self):
        if self.h is not None:
            L.sane_close(self.h)
        self.h = None

    def select(self, name):
        if not self.lock.acquire(timeout=3):
            raise Busy("The scanner is busy")
        try:
            self.want, self.user_values = name, {}
            self._close()
            self._open()
        finally:
            self.lock.release()

    # --- options

    def _descs(self):
        n = ctypes.c_int()
        check(L.sane_control_option(self.h, 0, GET, ctypes.byref(n), None))
        return [(i, L.sane_get_option_descriptor(self.h, i).contents) for i in range(1, n.value)]

    def _find(self, name):
        for i, d in self._descs():
            if d.name and d.name.decode() == name:
                return i, d
        raise KeyError(f"Unknown option: {name}")

    def _get(self, i, d):
        if d.type in (BUTTON, GROUP) or d.cap & CAP_INACTIVE:
            return None
        buf = ctypes.create_string_buffer(max(d.size, 1))
        check(L.sane_control_option(self.h, i, GET, buf, None))
        if d.type == STRING:
            return buf.value.decode("utf-8", "replace")
        words = struct.unpack(f"{d.size // 4}i", buf.raw[:d.size])
        vals = [w / 65536 if d.type == FIXED else bool(w) if d.type == BOOL else w for w in words]
        return vals[0] if len(vals) == 1 else vals

    def _set(self, name, value):
        i, d = self._find(name)
        if d.type == BUTTON:
            buf = None
        elif d.type == STRING:
            raw = str(value).encode()
            if len(raw) >= d.size:
                raise ValueError(f"{name}: value too long")
            buf = ctypes.create_string_buffer(raw, d.size)
        else:
            vals = value if isinstance(value, list) else [value]
            if len(vals) != d.size // 4:
                raise ValueError(f"{name}: expected {d.size // 4} value(s)")
            scale = 65536 if d.type == FIXED else 1
            buf = (ctypes.c_int * len(vals))(*[round(float(v) * scale) for v in vals])
        check(L.sane_control_option(self.h, i, SET, buf, None))
        return d

    @staticmethod
    def _constraint(d):
        conv = (lambda w: w / 65536) if d.type == FIXED else (lambda w: w)
        c = d.constraint
        if d.constraint_type == 1:
            r = c.range.contents
            return {"range": [conv(r.min), conv(r.max), conv(r.quant)]}
        if d.constraint_type == 2:
            return {"list": [conv(c.word_list[k]) for k in range(1, c.word_list[0] + 1)]}
        if d.constraint_type == 3:
            out, k = [], 0
            while c.string_list[k]:
                out.append(txt(c.string_list[k]))
                k += 1
            return {"list": out}
        return {}

    def _describe_all(self):
        out, group = [], ""
        for i, d in self._descs():
            if d.type == GROUP:
                group = txt(d.title)
                continue
            if not d.name:
                continue
            o = {"name": d.name.decode(), "title": txt(d.title) or d.name.decode(), "desc": txt(d.desc),
                 "group": group, "type": TYPES[d.type], "unit": UNITS[d.unit] if d.unit < len(UNITS) else "",
                 "count": d.size // 4 if d.type in (BOOL, INT, FIXED) else 1,
                 "active": not (d.cap & CAP_INACTIVE), "settable": bool(d.cap & CAP_SOFT_SELECT),
                 "advanced": bool(d.cap & CAP_ADVANCED), "hardware": bool(d.cap & CAP_HARD_SELECT)}
            o.update(self._constraint(d))
            if o["hardware"]:  # never read here: reading a button "consumes" the press
                o["action"] = BUTTONS.get(o["name"], BUTTONS["scan"])[2]
            elif o["active"] and o["count"] == 1 and d.type != BUTTON:
                o["value"] = self._get(i, d)
            out.append(o)
        return out

    def options(self):
        with self.session():
            return self._describe_all()

    def set_options(self, values):
        with self.session():
            for k, v in values.items():
                if self._set(k, v).type != BUTTON:
                    self.user_values.pop(k, None)
                    self.user_values[k] = v
            return self._describe_all()

    # --- scanning

    def set_output(self, fmt, quality):
        """Format used by the scanner's own Scan button."""
        if fmt not in FORMATS:
            raise ValueError(f"Unknown format: {fmt}")
        self.last_format, self.last_quality = fmt, max(1, min(100, int(quality)))

    def start(self, kind, fmt="png", quality=85, then=None, from_button=False):
        if self.job["state"] == "running":
            raise Busy("A scan is already running")
        if fmt not in FORMATS:
            raise ValueError(f"Unknown format: {fmt}")
        quality = max(1, min(100, int(quality)))
        if kind == "scan" and not from_button:
            self.set_output(fmt, quality)
        self._cancel = False
        self.job = {"id": self.job["id"] + 1, "state": "running", "kind": kind, "progress": 0}
        threading.Thread(target=self._run, args=(self.job, kind, fmt, quality, then), daemon=True).start()
        return dict(self.job)

    def cancel(self):
        self._cancel = True
        return dict(self.job)

    def _run(self, job, kind, fmt, quality, then):
        try:
            for attempt in (1, 2):
                try:
                    with self.session():
                        png = self._preview() if kind == "preview" else self._acquire(new_path("scan", ".png"))
                    break
                except SaneError as e:  # USB hiccup: the session reconnected, try once more
                    if e.status != IO_ERROR or attempt == 2:
                        raise
            if kind == "scan":
                out = convert(png, fmt, quality)
                job["file"] = out.name
                if then:
                    then(out)
            job["state"] = "done"
        except Cancelled:
            job["state"] = "cancelled"
        except Exception as e:
            job.update(state="error", error=str(e))

    def _dpi(self):
        for name in ("resolution", "x-resolution"):
            try:
                return float(self._get(*self._find(name)))
            except (KeyError, SaneError, TypeError):
                pass
        return 72.0

    def _preview(self):
        """Low-resolution scan of the whole glass; the user's own settings are restored afterwards."""
        keep, plan = {}, {}
        for name in ("resolution", "tl-x", "tl-y", "br-x", "br-y", "preview"):
            try:
                i, d = self._find(name)
            except KeyError:
                continue
            keep[name] = self._get(i, d)
            c = self._constraint(d)
            if name == "preview":
                plan[name] = True
            elif "range" in c:
                lo, hi = c["range"][:2]
                plan[name] = hi if name.startswith("br") else max(lo, 75) if name == "resolution" else lo
            elif "list" in c and name == "resolution":
                plan[name] = min([v for v in c["list"] if v >= 50] or c["list"])
        try:
            for k, v in plan.items():
                self._set(k, v)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp, "preview.png")
                self._acquire(path)
                self.preview = path.read_bytes()
        finally:
            for k, v in keep.items():
                if v is not None:
                    try:
                        self._set(k, v)
                    except (SaneError, ValueError):
                        pass

    def _acquire(self, path):
        dpi = self._dpi()
        check(L.sane_start(self.h))
        try:
            p = Parameters()
            check(L.sane_get_parameters(self.h, ctypes.byref(p)))
            if p.format not in (FRAME_GRAY, FRAME_RGB):
                # ponytail: single-pass only; three-pass (R, G, B frames) scanners are pre-2000 hardware
                raise RuntimeError("Three-pass scanners are not supported")
            png = PngWriter(path, p.pixels_per_line, p.bytes_per_line, p.depth, 3 if p.format == FRAME_RGB else 1, dpi)
            try:
                total, done, n = p.bytes_per_line * p.lines, 0, ctypes.c_int()
                buf = ctypes.create_string_buffer(1 << 17)
                while True:
                    if self._cancel:
                        raise Cancelled()
                    status = L.sane_read(self.h, buf, len(buf), ctypes.byref(n))
                    if status == EOF:
                        break
                    check(status)
                    png.write(ctypes.string_at(buf, n.value))
                    done += n.value
                    self.job["progress"] = round(done / total, 4) if total > 0 else None
                png.close()
            except BaseException:
                png.abort()
                raise
        finally:
            L.sane_cancel(self.h)
        return Path(path)

    # --- background: hardware buttons and auto-reconnect

    def watch(self):
        while True:
            time.sleep(0.3)
            if self.job["state"] == "running" or (self.h is None and time.time() < self._next_try):
                continue
            if not self.lock.acquire(blocking=False):
                continue
            pressed = []
            try:
                if self.h is None:
                    self._next_try = time.time() + 5
                    self._open()
                for i, d in self._descs():
                    if d.type == BOOL and d.cap & CAP_HARD_SELECT and not d.cap & CAP_INACTIVE and self._get(i, d):
                        pressed.append(d.name.decode())
            except Exception as e:
                self._close()
                self.error = str(e)
            finally:
                self.lock.release()
            for name in pressed:
                self.on_button(name)

    def on_button(self, name):
        fmt, then, _ = BUTTONS.get(name, BUTTONS["scan"])
        self.event_id += 1
        self.events = (self.events + [{"id": self.event_id, "button": name}])[-20:]
        try:
            self.start("scan", fmt or self.last_format, self.last_quality, then, from_button=True)
        except Busy:
            pass

    def state(self):
        return {"connected": self.h is not None, "device": self.device, "error": self.error,
                "devices": [{"name": d["name"], "label": f"{d['vendor']} {d['model']}"} for d in self.devices],
                "job": dict(self.job), "events": self.events[-10:],
                "outdir": str(OUT).replace(str(Path.home()), "~", 1), "format": self.last_format}


# ---------------------------------------------------------------- web server

class Handler(BaseHTTPRequestHandler):
    server_version = "ScanRevive"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        if not path or not path.is_file():
            return self._send(404, {"error": "Not found"})
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _trusted(self):
        # Blocks DNS rebinding: when bound to this computer only, answer only to local host names.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return not LOOPBACK or host in ("localhost", "127.0.0.1", "[::1]")

    def _guard(self, fn):
        try:
            fn()
        except Busy as e:
            self._send(409, {"error": str(e)})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": str(e).strip("'\"")})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        if not self._trusted():
            return self._send(403, {"error": "Forbidden"})
        path = unquote(urlparse(self.path).path)
        routes = {
            "/": lambda: self._file(HERE / "index.html"),
            "/api/state": lambda: self._send(200, SCANNER.state()),
            "/api/options": lambda: self._send(200, {"options": SCANNER.options()}),
            "/api/scans": lambda: self._send(200, {"scans": list_scans()}),
            "/api/preview.png": lambda: self._send(200, SCANNER.preview, "image/png") if SCANNER.preview
            else self._send(404, {"error": "No preview yet"}),
        }
        if path in routes:
            return self._guard(routes[path])
        if path.startswith("/scans/"):
            return self._guard(lambda: self._file(scan_path(path[7:])))
        if path.startswith("/thumbs/"):
            return self._guard(lambda: self._file(thumbnail(path[8:])))
        self._send(404, {"error": "Not found"})

    def do_POST(self):
        # Requiring JSON makes browsers send a CORS preflight, which we never accept: no cross-site requests.
        if not self._trusted() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._send(403, {"error": "Forbidden"})
        size = int(self.headers.get("Content-Length") or 0)
        if size > 4_000_000:
            return self._send(413, {"error": "Request too large"})
        try:
            body = json.loads(self.rfile.read(size) or b"{}")
        except ValueError:
            return self._send(400, {"error": "Invalid JSON"})
        ok = lambda data=None: self._send(200, data or {"ok": True})
        routes = {
            "/api/options": lambda: ok({"options": SCANNER.set_options(body["values"])}),
            "/api/device": lambda: ok(SCANNER.select(body["name"])),
            "/api/output": lambda: ok(SCANNER.set_output(body["format"], body.get("quality", 85))),
            "/api/preview": lambda: ok(SCANNER.start("preview")),
            "/api/scan": lambda: ok(SCANNER.start("scan", body.get("format", "png"), body.get("quality", 85))),
            "/api/cancel": lambda: ok(SCANNER.cancel()),
            "/api/pdf": lambda: ok({"file": combine(body["files"], body.get("quality", 85)).name}),
            "/api/open-folder": lambda: ok(run("open" if sys.platform == "darwin" else "xdg-open", OUT) and None),
        }
        path = urlparse(self.path).path
        if path not in routes:
            return self._send(404, {"error": "Not found"})
        self._guard(routes[path])


def combine(names, quality):
    paths = [scan_path(n) for n in names]
    if not paths or None in paths or any(p.suffix.lower() == ".pdf" for p in paths):
        raise ValueError("Pick one or more image scans to combine")
    return make_pdf(paths, new_path("document", ".pdf"), max(1, min(100, int(quality))))


# ---------------------------------------------------------------- self-check (no scanner needed)

def selftest():
    def decode(p):
        raw, idat, pos = Path(p).read_bytes(), b"", 8
        while pos < len(raw):
            n, tag = struct.unpack(">I4s", raw[pos:pos + 8])
            data = raw[pos + 8:pos + 8 + n]
            assert struct.unpack(">I", raw[pos + 8 + n:pos + 12 + n])[0] == zlib.crc32(tag + data), "bad CRC"
            if tag == b"IHDR":
                w, h = struct.unpack(">II", data[:8])
            idat += data if tag == b"IDAT" else b""
            pos += 12 + n
        pix = zlib.decompress(idat)
        stride = len(pix) // h
        assert all(pix[r * stride] == 0 for r in range(h))
        return w, h, b"".join(pix[r * stride + 1:(r + 1) * stride] for r in range(h))

    global OUT
    with tempfile.TemporaryDirectory() as tmp:
        OUT = Path(tmp)
        swapped = b"\x02\x01\x04\x03" if sys.byteorder == "little" else b"\x01\x02\x03\x04"
        cases = [  # name, width, bytes/line, depth, channels, scanner data, expected PNG pixels
            ("rgb", 3, 9, 8, 3, bytes(range(18)), bytes(range(18))),
            ("g16", 2, 4, 16, 1, b"\x01\x02\x03\x04", swapped),
            ("bw", 9, 2, 1, 1, b"\xff\x80", b"\x00\x7f"),
            ("padded", 2, 3, 8, 1, b"\x01\x02\xee\x03\x04\xee", b"\x01\x02\x03\x04"),
        ]
        for name, w, bpl, depth, ch, data, want in cases:
            png = PngWriter(OUT / f"{name}.png", w, bpl, depth, ch, 300)
            png.write(data[:5])  # lines split across reads, like real USB transfers
            png.write(data[5:])
            assert png.close() == (w, len(data) // bpl), name
            assert decode(OUT / f"{name}.png") == (w, len(data) // bpl, want), name
        assert scan_path("rgb.png") and not scan_path("../rgb.png") and not scan_path(".thumbs")
        if shutil.which("sips"):
            pdf = combine(["rgb.png", "g16.png"], 80).read_bytes()
            assert pdf.startswith(b"%PDF-1.4") and pdf.count(b"/Type /Page ") == 2
            xref = int(pdf.rsplit(b"startxref\n", 1)[1].split()[0])
            for k, line in enumerate(pdf[xref:].split(b"\n")[3:3 + 7], 1):
                assert pdf[int(line[:10]):].startswith(b"%d 0 obj" % k), "bad xref"
            assert convert(OUT / "rgb.png", "jpeg", 80).suffix == ".jpg"
    print("selftest OK")


def main():
    global L, OUT, SCANNER, LOOPBACK
    ap = argparse.ArgumentParser(description="Web interface for SANE scanners (Canon LiDE 110 and many others).")
    ap.add_argument("--port", type=int, default=8110)
    ap.add_argument("--host", default="127.0.0.1",
                    help="address to listen on; 0.0.0.0 lets phones and other computers in your network scan "
                         "(there is no password!)")
    ap.add_argument("--out", default="~/Pictures/ScanRevive", help="folder where scans are saved")
    ap.add_argument("--device", default="", help="pick a scanner by (part of) its name, e.g. 'LiDE 110'")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser on start")
    ap.add_argument("--selftest", action="store_true", help="check the image/PDF code and exit")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    L = load_libsane()
    OUT = Path(a.out).expanduser()
    OUT.mkdir(parents=True, exist_ok=True)
    LOOPBACK = a.host in ("127.0.0.1", "localhost", "::1")
    SCANNER = Scanner(a.device)
    threading.Thread(target=SCANNER.watch, daemon=True).start()
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    url = f"http://localhost:{a.port}/"
    print(f"ScanRevive is running at {url}\nScans are saved to {OUT}\nPress Ctrl+C to quit.")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if SCANNER.lock.acquire(timeout=5):
            SCANNER._close()
            L.sane_exit()


if __name__ == "__main__":
    main()
