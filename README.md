# ScanRevive

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon%20%7C%20Intel-black?logo=apple)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)

**Keep your Canon LiDE 110, and many other scanners, working on modern macOS, including Apple Silicon (M1–M5).**

Canon no longer ships drivers for many perfectly good scanners, so they stop working after a macOS update and often end up as e-waste.
ScanRevive brings them back with a simple web page that runs on your own Mac. You need no drivers, accounts or internet connection.

🌍 **[Quick start in your language](#-quick-start-in-your-language)**: Italiano · Español · Français · Deutsch · Português · Nederlands · Polski · Русский · Українська · Türkçe · العربية · हिन्दी · 中文 · 日本語 · 한국어 · Bahasa Indonesia · Tiếng Việt

---

## Features

- **Preview and crop**: scan the whole glass at low resolution, then drag to choose the area.
- **All scanner settings**: color or gray, 75 to 4800 dpi, 8 or 16-bit, brightness, contrast, gamma, lamp timer, calibration. The controls are built from what the scanner reports, so nothing is hidden.
- **PNG, JPEG, TIFF and PDF** output. PDFs keep the real paper size, so an A4 page stays A4.
- **Multi-page PDF**: tick the scans in the order you want and combine them into one document.
- **The scanner's own buttons work** (LiDE 110: COPY, SCAN, PDF, E-MAIL). See [Scanner buttons](#scanner-buttons).
- **Robust**: reconnects by itself when the scanner is unplugged or changes USB address, retries once after a USB hiccup, and a scan is never lost when a conversion fails.
- **Private**: everything stays on your computer. There is no telemetry and no cloud. By default only your own Mac can open the page.
- **Tiny**: one Python file and one HTML file. There is no pip, npm or build step.
- Works on phones and tablets too, when you [enable network access](#scan-from-your-phone-or-another-computer).

## Requirements

- macOS on Apple Silicon or Intel
- [Homebrew](https://brew.sh)
- Python 3.9 or newer, which comes with the Xcode Command Line Tools that Homebrew installs

## Quick start

If you don't have Homebrew yet, install it first by following the one-line instructions on [brew.sh](https://brew.sh).
At the end of its installation, Homebrew prints a few **Next steps** commands. Run them, or the `brew` command won't be found.

Then open **Terminal** and run:

```bash
brew install sane-backends
git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
python3 ~/ScanRevive/scanrevive.py
```

Your browser opens **http://localhost:8110**. Then:

1. Press **Preview** to see the glass.
2. Drag on the preview to choose the area. Pick the resolution and file format.
3. Press **Scan**. Files are saved in `~/Pictures/ScanRevive`.

> The first scan after switching on takes about 15 seconds while the lamp warms up and the scanner calibrates. Later scans are faster.

## Everyday use

| To… | Do this |
|---|---|
| **Start ScanRevive** | Double-click **`ScanRevive.command`** in the `ScanRevive` folder in your home folder. A Terminal window opens and the page appears in your browser. Keep the Terminal window open while you scan. |
| **Scan one page** | Put it face down on the glass, press **Preview**, drag a box around it, choose the file format and press **Scan**. It appears under **Scans**. Click it to open it. |
| **Make a PDF of several pages** | Scan each page, using JPEG for small files. Under **Scans**, tick the pages in order, then press **Combine … into PDF**. |
| **Scan without touching the computer** | Press a [button on the scanner](#scanner-buttons). |
| **Find your files** | Press **Open folder**, or in Finder go to **Pictures → ScanRevive**. |
| **Stop ScanRevive** | Close the Terminal window. |

**Which resolution?** 300 dpi suits documents, 600 dpi suits photos, and 1200 dpi or more suits small originals such as stamps or slides. Higher resolutions are slower and make bigger files.

## Supported scanners

| Scanner | Status |
|---|---|
| Canon CanoScan LiDE 110 | ✅ Tested on macOS 27, Apple M4: preview, crop, all formats, 16-bit, multi-page PDF, SCAN/PDF/E-MAIL buttons |
| Other Canon LiDE models (35, 60, 100, 120, 200, 210, 220, …) | Should work: same SANE `genesys` driver |
| Any scanner [supported by SANE](http://www.sane-project.org/sane-supported-devices.html) | Should work: the interface adapts to each scanner's options |

Not sure about yours? With the scanner plugged in, run `scanimage -L`. If it lists your scanner, ScanRevive can use it.
Please [open an issue](../../issues) to report whether your model works, so this table can grow.

## Scanner buttons

While ScanRevive is running, the buttons on the scanner work:

| Button | What it does |
|---|---|
| **SCAN** | Scans with the current settings and file format |
| **PDF** | Scans to a PDF |
| **E-MAIL** | Scans to JPEG and opens a new Mail message with the file attached |
| **COPY** | Scans and prints on your default printer, like a photocopier |

To have the buttons always ready, [start ScanRevive automatically at login](#start-automatically-at-login).

## Command-line options

```text
python3 scanrevive.py [--port 8110] [--host 127.0.0.1] [--out ~/Pictures/ScanRevive]
                      [--device "LiDE 110"] [--no-browser] [--selftest]
```

| Option | Meaning |
|---|---|
| `--port` | Web page port (default `8110`) |
| `--host` | Address to listen on. `127.0.0.1` means this Mac only. `0.0.0.0` means your whole network. |
| `--out` | Folder where scans are saved |
| `--device` | Pick a scanner by part of its name, when several are connected |
| `--no-browser` | Don't open the browser on start |
| `--selftest` | Check the image and PDF code without a scanner, then exit |

## Start automatically at login

ScanRevive can run in the background from the moment you log in. The scanner buttons then always work, and the page is always at http://localhost:8110.
Paste this into Terminal. It assumes you cloned into `~/ScanRevive` as in the Quick start.

```bash
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/io.github.scanrevive.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>io.github.scanrevive</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$HOME/ScanRevive/scanrevive.py</string>
    <string>--no-browser</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
EOF
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/io.github.scanrevive.plist
```

To turn it off again:

```bash
launchctl bootout gui/$(id -u)/io.github.scanrevive
rm ~/Library/LaunchAgents/io.github.scanrevive.plist
```

## Scan from your phone or another computer

```bash
python3 ~/ScanRevive/scanrevive.py --host 0.0.0.0
```

Then open `http://<your-mac-name>.local:8110` on any device in the same network.

> ⚠️ There is no password. Anyone on the same network can scan and see your scans. Only do this on a network you trust.

## Troubleshooting

| Problem | Fix |
|---|---|
| `brew: command not found` | Run the **Next steps** commands that Homebrew printed at the end of its installation, then open a new Terminal window. |
| macOS asks to install "command line developer tools" | Click **Install**. This provides `python3` and `git`. |
| "No scanner found" | Check the cable, then run `scanimage -L`. The LiDE is powered over USB, so plug it straight into the Mac or into a powered hub. |
| "Error during device I/O" | Unplug the scanner and plug it back in. ScanRevive reconnects within a few seconds. |
| "The scanner is busy" | Another program, or a second ScanRevive window started from Terminal, is using it. Close that program. |
| Stripes or odd colors | Tick **Show advanced options**, then press **Clear calibration cache** or **Force calibration**. |
| Port 8110 already in use | Start with `--port 8111`. |
| JPEG, TIFF or PDF fail on Linux | The conversions use `sips`, which is built into macOS. On Linux, use PNG. |

## Update and uninstall

To update to the latest version:

```bash
git -C ~/ScanRevive pull
```

To uninstall, first turn off the [login item](#start-automatically-at-login) if you set it up. Then run:

```bash
rm -rf ~/ScanRevive
brew uninstall sane-backends
```

Your scans stay in `~/Pictures/ScanRevive` until you delete them.

## FAQ

**Will the scanner show up in Image Capture, Preview or Photoshop?**
No. ScanRevive is its own small app that runs in your browser. Your scans are ordinary files, so you can open them in any program.

**Does it upload my documents anywhere?**
No. Nothing leaves your Mac. The page is served by your own computer, and by default no other device can open it.

**Does it cost anything?**
No. ScanRevive is free and open source under the MIT license.

**Windows?**
ScanRevive is made for macOS. On Linux the scanning engine and PNG output work. Windows is not supported.

## How it works

```text
Browser  ⇄  scanrevive.py (HTTP server)  ⇄  libsane via ctypes  ⇄  SANE "genesys" driver  ⇄  libusb  ⇄  scanner
```

[SANE](http://www.sane-project.org/) already contains an excellent open-source driver for these scanners, and it runs on Apple Silicon.
What was missing on modern macOS was an easy way to use it. ScanRevive talks to `libsane` directly through Python's built-in `ctypes`:

- It keeps the scanner open between scans. The LiDE 110 changes its USB address after every close, which confuses other front-ends.
- It streams the scan straight into a PNG file, so big scans don't fill your memory.
- It uses macOS's built-in `sips` for JPEG and TIFF and writes PDFs itself.
- It rejects requests from other websites, both cross-site and DNS rebinding, so web pages cannot scan or read your documents.

## Contributing

Contributions are welcome, especially:

- **Reports for other scanner models**, working or not. Include the output of `scanimage -L`.
- **Translations** of this README.
- Bug fixes. Please keep the project free of dependencies: Python standard library only.

Before sending a change, run `python3 scanrevive.py --selftest`.

## Credits

All the hard work of talking to the hardware is done by the [SANE project](http://www.sane-project.org/), especially its `genesys` driver.
The SANE developers reverse-engineered these scanners and have kept them alive for over two decades. Thank you.

## License

[MIT](LICENSE). SANE is installed separately and keeps its own license.
Canon, CanoScan and LiDE are trademarks of Canon Inc. This project is not affiliated with or endorsed by Canon.

---

## 🌍 Quick start in your language

<details>
<summary><b>Italiano</b></summary>

**ScanRevive** fa funzionare di nuovo lo scanner Canon LiDE 110 (e molti altri) sui Mac moderni, anche con Apple Silicon, quando i driver ufficiali non esistono più. Si usa dal browser, tutto resta sul tuo computer e non serve internet.

1. Installa [Homebrew](https://brew.sh), poi apri il **Terminale** e scrivi:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Il browser si apre su http://localhost:8110: premi **Preview**, trascina per scegliere l'area e premi **Scan**. Le scansioni vengono salvate in `~/Pictures/ScanRevive` (Immagini).
3. Le volte successive basta un doppio clic su `ScanRevive.command`, nella cartella `ScanRevive` della tua cartella Inizio.

I tasti dello scanner (COPY, SCAN, PDF, E-MAIL) funzionano mentre ScanRevive è aperto.
</details>

<details>
<summary><b>Español</b></summary>

**ScanRevive** hace que el escáner Canon LiDE 110 (y muchos otros) vuelva a funcionar en los Mac modernos, incluidos los Apple Silicon, aunque ya no existan controladores oficiales. Se usa desde el navegador, todo se queda en tu ordenador y no necesita internet.

1. Instala [Homebrew](https://brew.sh), abre el **Terminal** y escribe:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. El navegador se abre en http://localhost:8110: pulsa **Preview**, arrastra para elegir el área y pulsa **Scan**. Los escaneos se guardan en `~/Pictures/ScanRevive` (Imágenes).
3. Las próximas veces basta con hacer doble clic en `ScanRevive.command`, dentro de la carpeta `ScanRevive` de tu carpeta de inicio.

Los botones del escáner (COPY, SCAN, PDF, E-MAIL) funcionan mientras ScanRevive está abierto.
</details>

<details>
<summary><b>Français</b></summary>

**ScanRevive** redonne vie au scanner Canon LiDE 110 (et à bien d'autres) sur les Mac récents, y compris Apple Silicon, alors que les pilotes officiels n'existent plus. Il s'utilise depuis le navigateur, tout reste sur votre ordinateur et aucune connexion internet n'est nécessaire.

1. Installez [Homebrew](https://brew.sh), ouvrez le **Terminal** et tapez :
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Le navigateur s'ouvre sur http://localhost:8110 : cliquez sur **Preview**, faites glisser pour choisir la zone, puis cliquez sur **Scan**. Les numérisations sont enregistrées dans `~/Pictures/ScanRevive` (Images).
3. Les fois suivantes, double-cliquez simplement sur `ScanRevive.command`, dans le dossier `ScanRevive` de votre dossier personnel.

Les boutons du scanner (COPY, SCAN, PDF, E-MAIL) fonctionnent tant que ScanRevive est ouvert.
</details>

<details>
<summary><b>Deutsch</b></summary>

**ScanRevive** bringt den Canon LiDE 110 (und viele andere Scanner) auf aktuellen Macs wieder zum Laufen, auch mit Apple Silicon, obwohl es keine offiziellen Treiber mehr gibt. Bedient wird er im Browser. Alles bleibt auf deinem Computer, Internet ist nicht nötig.

1. Installiere [Homebrew](https://brew.sh), öffne das **Terminal** und gib ein:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Der Browser öffnet http://localhost:8110: Klicke auf **Preview**, ziehe einen Rahmen um den gewünschten Bereich und klicke auf **Scan**. Die Scans landen in `~/Pictures/ScanRevive` (Bilder).
3. Beim nächsten Mal genügt ein Doppelklick auf `ScanRevive.command` im Ordner `ScanRevive` in deinem Benutzerordner.

Die Tasten am Scanner (COPY, SCAN, PDF, E-MAIL) funktionieren, solange ScanRevive läuft.
</details>

<details>
<summary><b>Português</b></summary>

**ScanRevive** faz o scanner Canon LiDE 110 (e muitos outros) voltar a funcionar nos Macs modernos, inclusive com Apple Silicon, mesmo sem drivers oficiais. É usado pelo navegador, tudo fica no seu computador e não precisa de internet.

1. Instale o [Homebrew](https://brew.sh), abra o **Terminal** e digite:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. O navegador abre em http://localhost:8110: clique em **Preview**, arraste para escolher a área e clique em **Scan**. As digitalizações são salvas em `~/Pictures/ScanRevive` (Imagens).
3. Nas próximas vezes, basta clicar duas vezes em `ScanRevive.command`, na pasta `ScanRevive` da sua pasta pessoal.

Os botões do scanner (COPY, SCAN, PDF, E-MAIL) funcionam enquanto o ScanRevive estiver aberto.
</details>

<details>
<summary><b>Nederlands</b></summary>

**ScanRevive** laat de Canon LiDE 110 (en veel andere scanners) weer werken op moderne Macs, ook met Apple Silicon, terwijl er geen officiële drivers meer zijn. Je bedient hem via de browser. Alles blijft op je computer en er is geen internet nodig.

1. Installeer [Homebrew](https://brew.sh), open **Terminal** en typ:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. De browser opent http://localhost:8110: klik op **Preview**, sleep om het gebied te kiezen en klik op **Scan**. Scans worden opgeslagen in `~/Pictures/ScanRevive` (Afbeeldingen).
3. De volgende keer dubbelklik je gewoon op `ScanRevive.command` in de map `ScanRevive` in je thuismap.

De knoppen op de scanner (COPY, SCAN, PDF, E-MAIL) werken zolang ScanRevive draait.
</details>

<details>
<summary><b>Polski</b></summary>

**ScanRevive** przywraca do działania skaner Canon LiDE 110 (i wiele innych) na nowoczesnych komputerach Mac, także z Apple Silicon, mimo braku oficjalnych sterowników. Obsługuje się go w przeglądarce. Wszystko zostaje na Twoim komputerze, internet nie jest potrzebny.

1. Zainstaluj [Homebrew](https://brew.sh), otwórz **Terminal** i wpisz:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Przeglądarka otworzy http://localhost:8110: kliknij **Preview**, przeciągnij, aby zaznaczyć obszar, i kliknij **Scan**. Skany są zapisywane w `~/Pictures/ScanRevive` (Obrazki).
3. Następnym razem wystarczy dwukrotnie kliknąć `ScanRevive.command` w folderze `ScanRevive` w Twoim folderze domowym.

Przyciski na skanerze (COPY, SCAN, PDF, E-MAIL) działają, dopóki ScanRevive jest uruchomiony.
</details>

<details>
<summary><b>Русский</b></summary>

**ScanRevive** возвращает к жизни сканер Canon LiDE 110 (и многие другие) на современных Mac, в том числе на Apple Silicon, хотя официальных драйверов больше нет. Работает в браузере. Все данные остаются на вашем компьютере, интернет не нужен.

1. Установите [Homebrew](https://brew.sh), откройте **Терминал** и введите:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. В браузере откроется http://localhost:8110: нажмите **Preview**, выделите нужную область мышью и нажмите **Scan**. Сканы сохраняются в `~/Pictures/ScanRevive` (Изображения).
3. В следующий раз просто дважды щёлкните `ScanRevive.command` в папке `ScanRevive` вашей домашней папки.

Кнопки на сканере (COPY, SCAN, PDF, E-MAIL) работают, пока запущен ScanRevive.
</details>

<details>
<summary><b>Українська</b></summary>

**ScanRevive** повертає до життя сканер Canon LiDE 110 (і багато інших) на сучасних Mac, зокрема на Apple Silicon, хоча офіційних драйверів більше немає. Працює в браузері. Усі дані залишаються на вашому комп'ютері, інтернет не потрібен.

1. Встановіть [Homebrew](https://brew.sh), відкрийте **Термінал** і введіть:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. У браузері відкриється http://localhost:8110: натисніть **Preview**, виділіть потрібну область мишею і натисніть **Scan**. Скани зберігаються в `~/Pictures/ScanRevive` (Зображення).
3. Наступного разу просто двічі клацніть `ScanRevive.command` у папці `ScanRevive` вашої домашньої папки.

Кнопки на сканері (COPY, SCAN, PDF, E-MAIL) працюють, поки запущено ScanRevive.
</details>

<details>
<summary><b>Türkçe</b></summary>

**ScanRevive**, resmi sürücüleri artık bulunmayan Canon LiDE 110 tarayıcısını (ve birçok başka modeli) Apple Silicon dahil yeni Mac'lerde yeniden çalıştırır. Web tarayıcısından kullanılır. Her şey bilgisayarınızda kalır, internet gerekmez.

1. [Homebrew](https://brew.sh) kurun, **Terminal**'i açın ve şunu yazın:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Web tarayıcınızda http://localhost:8110 açılır: **Preview** düğmesine basın, alanı sürükleyerek seçin ve **Scan** düğmesine basın. Taramalar `~/Pictures/ScanRevive` (Resimler) klasörüne kaydedilir.
3. Sonraki seferlerde ana klasörünüzdeki `ScanRevive` klasöründe bulunan `ScanRevive.command` dosyasına çift tıklamanız yeterlidir.

Tarayıcının üzerindeki düğmeler (COPY, SCAN, PDF, E-MAIL), ScanRevive açık olduğu sürece çalışır.
</details>

<details>
<summary><b>العربية</b></summary>
<div dir="rtl">

**ScanRevive** يعيد تشغيل الماسح الضوئي Canon LiDE 110 (وطرازات أخرى كثيرة) على أجهزة Mac الحديثة، بما فيها أجهزة Apple Silicon، رغم توقّف التعريفات الرسمية. يُستخدم من خلال المتصفح، وتبقى كل بياناتك على جهازك دون الحاجة إلى الإنترنت.

1. ثبّت [Homebrew](https://brew.sh)، ثم افتح **Terminal** واكتب:

</div>

```bash
brew install sane-backends
git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
python3 ~/ScanRevive/scanrevive.py
```

<div dir="rtl">

2. سيفتح المتصفح الصفحة http://localhost:8110: اضغط **Preview**، واسحب لتحديد المنطقة، ثم اضغط **Scan**. تُحفظ الملفات في `~/Pictures/ScanRevive` (الصور).
3. في المرات التالية يكفي النقر المزدوج على `ScanRevive.command` داخل مجلد `ScanRevive` في مجلد المستخدم.

تعمل أزرار الماسح (COPY وSCAN وPDF وE-MAIL) ما دام ScanRevive قيد التشغيل.

</div>
</details>

<details>
<summary><b>हिन्दी</b></summary>

**ScanRevive** आपके Canon LiDE 110 स्कैनर (और कई अन्य मॉडल) को आधुनिक Mac पर, Apple Silicon सहित, फिर से चालू कर देता है, भले ही अब आधिकारिक ड्राइवर उपलब्ध न हों। इसे ब्राउज़र से इस्तेमाल किया जाता है। सब कुछ आपके कंप्यूटर पर ही रहता है, इंटरनेट की ज़रूरत नहीं।

1. [Homebrew](https://brew.sh) इंस्टॉल करें, फिर **Terminal** खोलकर लिखें:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. ब्राउज़र में http://localhost:8110 खुलेगा: **Preview** दबाएँ, माउस से क्षेत्र चुनें और **Scan** दबाएँ। स्कैन `~/Pictures/ScanRevive` में सेव होते हैं।
3. अगली बार बस होम फ़ोल्डर के `ScanRevive` फ़ोल्डर में `ScanRevive.command` पर डबल-क्लिक करें।

स्कैनर के बटन (COPY, SCAN, PDF, E-MAIL) तब तक काम करते हैं जब तक ScanRevive चल रहा है।
</details>

<details>
<summary><b>中文（简体）</b></summary>

**ScanRevive** 让 Canon LiDE 110 扫描仪（以及许多其他型号）在新款 Mac 上（包括 Apple Silicon）重新工作，即使官方驱动已不再提供。通过浏览器使用，所有数据都留在你的电脑上，无需联网。

1. 安装 [Homebrew](https://brew.sh)，然后打开 **终端** 并输入：
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. 浏览器会打开 http://localhost:8110：点击 **Preview**，拖动鼠标选择区域，再点击 **Scan**。扫描文件保存在 `~/Pictures/ScanRevive`（图片）中。
3. 以后只需双击个人文件夹中 `ScanRevive` 文件夹里的 `ScanRevive.command` 即可。

只要 ScanRevive 正在运行，扫描仪上的按键（COPY、SCAN、PDF、E-MAIL）就可以使用。
</details>

<details>
<summary><b>日本語</b></summary>

**ScanRevive** は、公式ドライバーが提供されなくなった Canon LiDE 110（およびその他多くのスキャナー）を、Apple Silicon を含む最新の Mac で再び使えるようにします。ブラウザーから操作し、データはすべてお使いのコンピューター内に留まります。インターネット接続は不要です。

1. [Homebrew](https://brew.sh) をインストールし、**ターミナル** を開いて次のように入力します：
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. ブラウザーで http://localhost:8110 が開きます。**Preview** を押し、ドラッグして範囲を選び、**Scan** を押してください。スキャンしたファイルは `~/Pictures/ScanRevive`（ピクチャ）に保存されます。
3. 次回からは、ホームフォルダーの `ScanRevive` フォルダーにある `ScanRevive.command` をダブルクリックするだけです。

ScanRevive の起動中は、スキャナー本体のボタン（COPY、SCAN、PDF、E-MAIL）も使えます。
</details>

<details>
<summary><b>한국어</b></summary>

**ScanRevive**는 공식 드라이버가 더 이상 제공되지 않는 Canon LiDE 110 스캐너(및 기타 여러 모델)를 Apple Silicon을 포함한 최신 Mac에서 다시 사용할 수 있게 해 줍니다. 웹 브라우저에서 사용하며, 모든 데이터가 컴퓨터 안에만 남으므로 인터넷이 필요 없습니다.

1. [Homebrew](https://brew.sh)를 설치한 다음 **터미널**을 열고 다음을 입력합니다:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. 브라우저에서 http://localhost:8110이 열리면 **Preview**를 누르고, 드래그해서 영역을 선택한 뒤 **Scan**을 누르세요. 스캔 파일은 `~/Pictures/ScanRevive`(사진)에 저장됩니다.
3. 다음부터는 홈 폴더의 `ScanRevive` 폴더에 있는 `ScanRevive.command`를 더블클릭하기만 하면 됩니다.

ScanRevive가 실행 중이면 스캐너의 버튼(COPY, SCAN, PDF, E-MAIL)도 사용할 수 있습니다.
</details>

<details>
<summary><b>Bahasa Indonesia</b></summary>

**ScanRevive** membuat pemindai Canon LiDE 110 (dan banyak model lain) berfungsi lagi di Mac modern, termasuk Apple Silicon, meskipun driver resminya sudah tidak tersedia. Digunakan melalui peramban web. Semua data tetap di komputer Anda, tanpa perlu internet.

1. Pasang [Homebrew](https://brew.sh), buka **Terminal**, lalu ketik:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Peramban akan membuka http://localhost:8110: tekan **Preview**, seret untuk memilih area, lalu tekan **Scan**. Hasil pindaian disimpan di `~/Pictures/ScanRevive` (Gambar).
3. Selanjutnya cukup klik dua kali `ScanRevive.command` di folder `ScanRevive` pada folder rumah Anda.

Tombol pada pemindai (COPY, SCAN, PDF, E-MAIL) berfungsi selama ScanRevive berjalan.
</details>

<details>
<summary><b>Tiếng Việt</b></summary>

**ScanRevive** giúp máy quét Canon LiDE 110 (và nhiều mẫu khác) hoạt động trở lại trên máy Mac đời mới, kể cả Apple Silicon, dù không còn driver chính thức. Sử dụng qua trình duyệt web. Mọi dữ liệu nằm trên máy của bạn, không cần internet.

1. Cài [Homebrew](https://brew.sh), mở **Terminal** và gõ:
   ```bash
   brew install sane-backends
   git clone https://github.com/paromeosi/scanrevive.git ~/ScanRevive
   python3 ~/ScanRevive/scanrevive.py
   ```
2. Trình duyệt sẽ mở http://localhost:8110: nhấn **Preview**, kéo chuột để chọn vùng cần quét rồi nhấn **Scan**. Bản quét được lưu trong `~/Pictures/ScanRevive` (Hình ảnh).
3. Những lần sau, chỉ cần nhấp đúp vào `ScanRevive.command` trong thư mục `ScanRevive` ở thư mục người dùng của bạn.

Các nút trên máy quét (COPY, SCAN, PDF, E-MAIL) hoạt động khi ScanRevive đang chạy.
</details>
