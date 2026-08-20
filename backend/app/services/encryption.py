"""
Encryption Service - Centralized encryption/decryption for API keys
Uses Fernet symmetric encryption (AES 128-bit)

Key derivation is STABLE across deployments: derived deterministically from
SECRET_KEY via SHA-256, so secrets survive redeploys and server disk wipes
(a `.env`-only key file is no longer required or committed). A legacy
`data/encryption.key` file is still honored as a fallback for rows encrypted
before the SECRET_KEY-derived key existed.
"""
import os
import json
import base64
import hashlib
from typing import Optional, Dict

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from app.config import settings


def _derive_key() -> bytes:
    """Derive a stable Fernet key from SECRET_KEY (32 bytes urlsafe b64)."""
    raw = hashlib.sha256((settings.SECRET_KEY or "change-this-in-production").encode()).digest()
    return base64.urlsafe_b64encode(raw)


def _load_legacy_file_key() -> Optional[bytes]:
    """Read the legacy data/encryption.key file if it still exists."""
    key_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "encryption.key"
    )
    try:
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return f.read()
    except Exception:  # noqa: BLE001
        return None
    return None


class EncryptionHelper:
    """Singleton encryption service for encrypting/decrypting sensitive data."""

    _instance = None
    _cipher = None
    _legacy_cipher = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._cipher is None and CRYPTO_AVAILABLE:
            self._init_ciphers()

    def _init_ciphers(self):
        """Build the primary (SECRET_KEY-derived) and legacy file-backed ciphers."""
        try:
            EncryptionHelper._cipher = Fernet(_derive_key())
        except Exception:  # noqa: BLE001
            EncryptionHelper._cipher = None
        legacy = _load_legacy_file_key()
        if legacy:
            try:
                EncryptionHelper._legacy_cipher = Fernet(legacy)
            except Exception:  # noqa: BLE001
                EncryptionHelper._legacy_cipher = None

    def encrypt(self, value: str) -> Optional[str]:
        """Encrypt a string value with the primary key."""
        if not value or not self._cipher:
            return value
        return self._cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> Optional[str]:
        """Decrypt a string value (primary, then legacy key, then as-is)."""
        if not value or not self._cipher:
            return value
        try:
            return self._cipher.decrypt(value.encode()).decode()
        except Exception:  # noqa: BLE001
            pass
        if self._legacy_cipher:
            try:
                return self._legacy_cipher.decrypt(value.encode()).decode()
            except Exception:  # noqa: BLE001
                pass
        return value  # Return as-is if decryption fails

    def encrypt_json(self, data: Dict) -> str:
        """Encrypt a dictionary as JSON string."""
        json_str = json.dumps(data)
        if not self._cipher:
            return json_str
        return self._cipher.encrypt(json_str.encode()).decode()

    def decrypt_json(self, value: str) -> Optional[Dict]:
        """Decrypt a JSON string back to dictionary (also tries legacy key)."""
        if not value:
            return None
        try:
            value_bytes = value.encode()
            if self._cipher:
                try:
                    return json.loads(self._cipher.decrypt(value_bytes).decode())
                except InvalidToken:
                    pass
            if self._legacy_cipher:
                try:
                    return json.loads(self._legacy_cipher.decrypt(value_bytes).decode())
                except Exception:  # noqa: BLE001
                    pass
            return json.loads(value)  # Fallback: assume not encrypted
        except Exception:  # noqa: BLE001
            return None


# Convenience functions
def encrypt_value(value: str) -> Optional[str]:
    """Encrypt a single value."""
    return EncryptionHelper().encrypt(value)

def decrypt_value(value: str) -> Optional[str]:
    """Decrypt a single value."""
    return EncryptionHelper().decrypt(value)

def encrypt_json(data: Dict) -> str:
    """Encrypt JSON data."""
    return EncryptionHelper().encrypt_json(data)

def decrypt_json(value: str) -> Optional[Dict]:
    """Decrypt JSON data."""
    return EncryptionHelper().decrypt_json(value)