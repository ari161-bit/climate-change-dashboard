"""Field-level encryption at rest (Fernet / AES-128-CBC + HMAC) with a key derived from SECRET_KEY."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

PREFIX = 'enc::'


def _fernet():
    digest = hashlib.sha256(('climate-field-encryption:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(text):
    if not text or text.startswith(PREFIX):
        return text
    return PREFIX + _fernet().encrypt(text.encode()).decode()


def decrypt(token):
    if not token or not token.startswith(PREFIX):
        return token
    try:
        return _fernet().decrypt(token[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return '[unreadable: the encryption key has changed]'
