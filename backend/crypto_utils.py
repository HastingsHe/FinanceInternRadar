"""
Encryption utilities for subscriber data.
Uses Fernet (AES-128-CBC + HMAC) with a key derived from a master secret.
"""

import hashlib
import base64
from cryptography.fernet import Fernet


def derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a secret string."""
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt(text: str, key: bytes) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    if not text:
        return text
    cipher = Fernet(key)
    return cipher.encrypt(text.encode()).decode()


def decrypt(token: str, key: bytes) -> str:
    """Decrypt a Fernet token back to plaintext."""
    if not token:
        return token
    try:
        cipher = Fernet(key)
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        return token  # fallback for unencrypted legacy data
