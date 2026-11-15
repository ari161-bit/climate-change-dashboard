"""Encryption at rest for climate data files (uploads, cleaned files, backups).

Fernet = AES-128-CBC + HMAC-SHA256, so files are both encrypted and tamper-evident.

Key: environment variable EARTHSCAPE_DATA_KEY, otherwise keys/data.key (created on
first use). Keep that file out of version control and back it up separately from
the data: without it encrypted files cannot be read.
"""
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_fernet = None
MAGIC = b"gAAAAA"   # every Fernet token starts with this (version byte, base64)


def key_path():
    return Path(settings.BASE_DIR) / "keys" / "data.key"


def _get():
    global _fernet
    if _fernet is None:
        key = os.environ.get("EARTHSCAPE_DATA_KEY", "").encode()
        if not key:
            p = key_path()
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(Fernet.generate_key())
            key = p.read_bytes().strip()
        _fernet = Fernet(key)
    return _fernet


def encrypt(data: bytes) -> bytes:
    return _get().encrypt(data)


def is_encrypted(data: bytes) -> bool:
    return data[:6] == MAGIC


def decrypt(data: bytes) -> bytes:
    """Decrypt, or return unchanged for files saved before encryption was enabled."""
    if not is_encrypted(data):
        return data
    try:
        return _get().decrypt(data)
    except InvalidToken as e:
        raise ValueError("File could not be decrypted (wrong key or the file was modified).") from e
