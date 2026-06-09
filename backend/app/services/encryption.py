"""
Encryption Service - Centralized encryption/decryption for API keys
Uses Fernet symmetric encryption (AES 128-bit)
Key stored in: backend/data/encryption.key
"""
import os
import json
from typing import Optional, Dict

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class EncryptionHelper:
    """Singleton encryption service for encrypting/decrypting sensitive data."""
    
    _instance = None
    _cipher = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._cipher is None and CRYPTO_AVAILABLE:
            self._init_cipher()
    
    def _init_cipher(self):
        """Load encryption key from file or create new one."""
        key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "encryption.key")
        
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                EncryptionHelper._cipher = Fernet(f.read())
        else:
            # Generate new key
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "wb") as f:
                f.write(key)
            EncryptionHelper._cipher = Fernet(key)
    
    def encrypt(self, value: str) -> Optional[str]:
        """Encrypt a string value."""
        if not value or not self._cipher:
            return value
        return self._cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, value: str) -> Optional[str]:
        """Decrypt a string value."""
        if not value or not self._cipher:
            return value
        try:
            return self._cipher.decrypt(value.encode()).decode()
        except Exception:
            return value  # Return as-is if decryption fails
    
    def encrypt_json(self, data: Dict) -> str:
        """Encrypt a dictionary as JSON string."""
        json_str = json.dumps(data)
        if not self._cipher:
            return json_str
        return self._cipher.encrypt(json_str.encode()).decode()
    
    def decrypt_json(self, value: str) -> Optional[Dict]:
        """Decrypt a JSON string back to dictionary."""
        if not value or not self._cipher:
            try:
                return json.loads(value) if value else None
            except:
                return None
        
        try:
            decrypted = self._cipher.decrypt(value.encode()).decode()
            return json.loads(decrypted)
        except:
            try:
                return json.loads(value)  # Fallback: assume not encrypted
            except:
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