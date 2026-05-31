"""
Encryption utilities for subscriber data.
Uses Fernet (AES-128-CBC + HMAC) with a key derived from a master secret.
"""

import hashlib
import base64
from cryptography.fernet import Fernet

# Master key — derived from project secret
_MASTER_SECRET = "FinanceInternRadar_UserVault_2026"
_key_bytes = hashlib.sha256(_MASTER_SECRET.encode()).digest()
_key = base64.urlsafe_b64encode(_key_bytes)
_cipher = Fernet(_key)


def encrypt(text: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    if not text:
        return text
    return _cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    if not token:
        return token
    try:
        return _cipher.decrypt(token.encode()).decode()
    except Exception:
        return token  # fallback for unencrypted legacy data
