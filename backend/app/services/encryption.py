"""Fernet-based symmetric encryption for IMAP credentials and API keys."""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _cipher() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set — generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'`"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string with Fernet. Returns the ciphertext as a utf-8 string."""
    if plaintext is None:
        raise ValueError("Cannot encrypt None")
    return _cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string. Raises InvalidToken on tampering."""
    if not ciphertext:
        return ""
    try:
        return _cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Invalid or corrupt ciphertext") from None
