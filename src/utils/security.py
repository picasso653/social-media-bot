from cryptography.fernet import Fernet

from src.config import settings


def _get_fernet() -> Fernet:
    key = settings.token_encryption_key
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()
