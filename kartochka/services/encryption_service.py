from __future__ import annotations

from kartochka.config import settings


class EncryptionService:
    def __init__(self) -> None:
        self._fernet = None
        if settings.encryption_key:
            from cryptography.fernet import Fernet

            self._fernet = Fernet(settings.encryption_key.encode())

    def encrypt(self, value: str) -> str:
        if self._fernet is None:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        if self._fernet is None:
            return encrypted
        return self._fernet.decrypt(encrypted.encode()).decode()


encryption_service = EncryptionService()
