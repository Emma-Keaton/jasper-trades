"""
SQLAlchemy model for per‑device crypto credentials (API keys, wallet address, chain)
Stored encrypted using the existing EncryptionHelper.
"""

from sqlalchemy import Column, Integer, String, DateTime
from app.models import Base  # Use the project's central declarative Base

class DeviceCryptoCredential(Base):
    __tablename__ = "device_crypto_credentials"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, nullable=False, index=True)  # X‑Device‑ID header value
    exchange = Column(String, nullable=False)  # e.g. "binance", "solana", "ethereum"
    encrypted_api_key = Column(String, nullable=True)
    encrypted_api_secret = Column(String, nullable=True)
    wallet_address = Column(String, nullable=True)
    chain = Column(String, nullable=True)  # "ethereum", "solana", "bsc", …
    created_at = Column(DateTime, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(
        DateTime,
        server_default="CURRENT_TIMESTAMP",
        onupdate="CURRENT_TIMESTAMP",
    )
