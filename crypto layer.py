import os, time, jwt
from functools import wraps
from flask import request, jsonify

JWT_SECRET_FILE = ".jwt_secret"
JWT_ALGO = "HS256"
JWT_TTL = 3600

def _load_or_create_secret() -> bytes:
    if os.path.exists(JWT_SECRET_FILE):
        with open(JWT_SECRET_FILE, "rb") as f:
            return f.read()
    secret = os.urandom(32)
    fd = os.open(JWT_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(secret)
    return secret

JWT_SECRET = _load_or_create_secret()

ROLES = {"viewer": 1, "operator": 2, "admin": 3}

def issue_token(username: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": username, "role": role, "iat": now, "exp": now + JWT_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def require_role(min_role: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            hdr = request.headers.get("Authorization", "")
            if not hdr.startswith("Bearer "):
                return jsonify({"error": "missing token"}), 401
            try:
                payload = jwt.decode(hdr[7:], JWT_SECRET, algorithms=[JWT_ALGO])
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "invalid token"}), 401
            if ROLES.get(payload.get("role"), 0) < ROLES[min_role]:
                return jsonify({"error": "forbidden"}), 403
            request.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator
