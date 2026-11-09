from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _get_fernet() -> Fernet:
    key = settings.DATASOURCES_ENCRYPTION_KEY
    if not key:
        # Dev fallback — generate ephemeral (data will not survive restart)
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(plain: str) -> bytes:
    if plain is None:
        raise ValueError("Cannot encrypt None")
    return _get_fernet().encrypt(plain.encode("utf-8"))


def decrypt(ct: bytes) -> str:
    if not ct:
        return ""
    return _get_fernet().decrypt(ct).decode("utf-8")
