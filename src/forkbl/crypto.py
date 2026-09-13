"""The CryptoJS-compatible form encryption used by shterm."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt_field(value: str, session_id: str) -> str:
    """Encrypt a login field in the format emitted by the web UI."""
    key = hashlib.md5(session_id.encode("utf-8")).digest()
    iv = secrets.token_bytes(16)
    data = value.encode("utf-8")
    padding = 16 - (len(data) % 16)
    padded = data + bytes([padding]) * padding
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    ciphertext_hex = ciphertext.hex().upper()
    digest = hmac.new(key, ciphertext_hex.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"__RIS_ENC{{{ciphertext_hex}@{iv.hex()}@{digest}}}"
