"""
Broker Connection Models

Stores device's connected broker accounts (cTrader, Binance, etc.)
with encrypted OAuth tokens for(auto-trading).

Authentication: Device ID fingerprint via localStorage (no user accounts)
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from datetime import datetime

# Import Base from database directly to avoid circular import with app.models file
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
from database import Base


class BrokerConnection(Base):
    """
    Device's connected broker account.

    Supports multiple brokers:
    - cTrader (OAuth 2.0) - FxPro, IronFX, etc.
    - Binance (API keys) - Crypto

    Security:
    - OAuth tokens encrypted at rest
    - API keys encrypted at rest
    - Never store plain text credentials
    
    Authentication: Uses device_id fingerprint instead of user accounts.
    """
    __tablename__ = "broker_connections"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), nullable=False, index=True)  # Device fingerprint

    # Broker type: 'ctrader', 'binance'
    broker_type = Column(String(20), nullable=False)

    # Broker account metadata
    broker_name = Column(String(100))
    account_id = Column(String(100))  # Broker's account ID
    account_currency = Column(String(3), default="USD")
    account_balance = Column(Float, default=0.0)

    # cTrader OAuth tokens
    ctrader_account_id = Column(String(100))
    encrypted_access_token = Column(Text)
    encrypted_refresh_token = Column(Text)
    token_expires_at = Column(DateTime)

    # Binance API keys
    encrypted_api_key = Column(Text)
    encrypted_api_secret = Column(Text)

    # Status
    is_active = Column(Boolean, default=True)  # Auto-trading enabled
    is_connected = Column(Boolean, default=False)  # Auth successful
    connection_status = Column(String(50))  # 'connected', 'expired', 'error'
    last_sync_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_token_expired(self) -> bool:
        """Check if OAuth token is expired or expiring within 24h"""
        if not self.token_expires_at:
            return True
        from datetime import timedelta
        return datetime.utcnow() > (self.token_expires_at - timedelta(hours=24))

    def __repr__(self):
        return f"<BrokerConnection(broker={self.broker_name}, type={self.broker_type})>"