import os, struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

KEY_LEN = 32
NONCE_LEN = 12
TAG_LEN = 16

def derive_key(shared_secret: bytes, salt: bytes = b"crock-v1") -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=salt,
        info=b"crock-session-key",
    ).derive(shared_secret)

def encrypt_packet(key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct

def decrypt_packet(key: bytes, packet: bytes) -> bytes:
    if len(packet) < NONCE_LEN + TAG_LEN:
        raise ValueError("packet too short")
    nonce, ct = packet[:NONCE_LEN], packet[NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ct, None)

def recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf

def send_frame(sock, key: bytes, plaintext: bytes):
    pkt = encrypt_packet(key, plaintext)
    sock.sendall(struct.pack("!I", len(pkt)) + pkt)

def recv_frame(sock, key: bytes) -> bytes:
    (n,) = struct.unpack("!I", recv_exact(sock, 4))
    if n > 64 * 1024 * 1024:
        raise ValueError("frame too large")
    return decrypt_packet(key, recv_exact(sock, n))
