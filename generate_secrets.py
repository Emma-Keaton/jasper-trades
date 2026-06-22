"""
Jasper Trades - Production Secret Generator
Run this script to generate all required secrets for production deployment.
Copy the output directly into Render environment variables.
"""
import secrets
from cryptography.fernet import Fernet

print("=" * 80)
print("JASPER TRADES - PRODUCTION SECRETS")
print("=" * 80)
print()
print("Copy these values into Render dashboard → Environment Variables")
print()
print("-" * 80)

# Generate SECRET_KEY (32 bytes, URL-safe base64 encoded)
secret_key = secrets.token_urlsafe(32)
print(f"SECRET_KEY={secret_key}")

# Generate API_AUTH_KEY
api_auth_key = "jasper_" + secrets.token_urlsafe(24)
print(f"API_AUTH_KEY={api_auth_key}")

# Generate encryption key for Fernet (AES encryption)
encryption_key = Fernet.generate_key().decode()
print(f"ENCRYPTION_KEY={encryption_key}")

# Generate cTrader encryption key
ctrader_key = secrets.token_urlsafe(32)
print(f"CTRADER_ENCRYPTION_KEY={ctrader_key}")

print()
print("-" * 80)
print()
print("IMPORTANT:")
print("1. Store these secrets securely")
print("2. Never commit them to git")
print("3. Rotate them every 90 days")
print("4. Use different keys for staging/production")
print()
print("=" * 80)
print("Secret generation complete!")
print("=" * 80)