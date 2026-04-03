"""Encrypt/decrypt user secrets (API keys, cookies)."""

import base64

from cryptography.fernet import Fernet

from ..config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not set — cannot encrypt/decrypt secrets")
    # Pad or hash the key to 32 bytes URL-safe base64
    if len(key) < 32:
        key = key.ljust(32, "0")
    key_bytes = base64.urlsafe_b64encode(key[:32].encode())
    return Fernet(key_bytes)


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
