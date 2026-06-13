"""
Token Encryption Service

Encrypts OAuth access/refresh tokens at rest using Fernet (AES-128).
Tokens are only decrypted in memory when making API calls.

Security:
- Encryption key stored in environment variable (never in code)
- Lost key = lost tokens (users must re-authorize)
- Backup your CTRADER_ENCRYPTION_KEY securely
"""

import os
from cryptography.fernet import Fernet, InvalidToken


def get_encryption_key() -> str:
    """Get encryption key from environment variable"""
    key = os.getenv("CTRADER_ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "CTRADER_ENCRYPTION_KEY not set. "
            "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return key


def encrypt_token(token: str) -> str:
    """
    Encrypt OAuth token before storing in database.
    
    Args:
        token: Plain text access/refresh token
        
    Returns:
        str: Encrypted token (base64-encoded)
    """
    key = get_encryption_key()
    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(token.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt OAuth token for API use.
    
    WARNING: Only call this in memory when making API calls.
    Never log or expose decrypted tokens.
    
    Args:
        encrypted_token: Encrypted token from database
        
    Returns:
        str: Decrypted plain text token
    """
    key = get_encryption_key()
    fernet = Fernet(key.encode())
    
    try:
        decrypted = fernet.decrypt(encrypted_token.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        raise Exception(
            "Failed to decrypt token. "
            "Possible causes: "
            "1) CTRADER_ENCRYPTION_KEY changed "
            "2) Token was corrupted "
            "3) Wrong encryption key format"
        )