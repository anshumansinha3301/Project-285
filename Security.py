from cryptography.fernet import Fernet
from django.conf import settings


def _cipher():
    return Fernet(
        settings.CREDENTIAL_ENCRYPTION_KEY.encode()
    )


def encrypt_password(password: str) -> str:
    return _cipher().encrypt(
        password.encode("utf-8")
    ).decode("utf-8")


def decrypt_password(encrypted: str) -> str:
    return _cipher().decrypt(
        encrypted.encode("utf-8")
    ).decode("utf-8")


def mask_secret(value: str) -> str:
    return "********" if value else ""
