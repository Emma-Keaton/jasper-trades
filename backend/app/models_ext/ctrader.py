"""
cTrader OAuth Trading Account Models

Multi-tenant copy-trading architecture with secure token storage.
Authentication: Device ID fingerprint via localStorage (no user accounts)
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

# Import Base from database directly (models_ext is not a proper package)
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
from database import Base


class TradingAccount(Base):
    """
    Device's cTrader trading account with OAuth tokens.

    Security: Access/refresh tokens are encrypted at rest using Fernet encryption.
    The encryption key must be set via CTRADER_ENCRYPTION_KEY environment variable.
    
    Authentication: Uses device_id fingerprint instead of user accounts.
    """
    __tablename__ = "trading_accounts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), nullable=False, index=True)  # Device fingerprint

    # Account type: 'ctrader' (default) or  (deprecated)
    account_type = Column(String(20), default="ctrader", nullable=False)

    # === cTrader OAuth Fields ===
    ctid_trader_account_id = Column(String(50), unique=True)  # From cTrader API
    ctid_account_name = Column(String(100))  # e.g., "FxPro Pro Account"

    # Encrypted tokens (NEVER store plain text!)
    encrypted_access_token = Column(Text)
    encrypted_refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    token_last_refreshed = Column(DateTime)

    # Account metadata from cTrader API
    broker_name = Column(String(50))  # e.g., 'FxPro', 'IronFX', 'Spotware'
    account_currency = Column(String(3), default="USD")
    account_leverage = Column(Float, default=1.0)
    account_balance = Column(Float, default=0.0)
    account_equity = Column(Float, default=0.0)

    # Status flags
    is_active = Column(Boolean, default=True)  # User can enable/disable bot
    is_connected = Column(Boolean, default=False)  # OAuth connection status
    connection_status = Column(String(50))  # 'connected', 'expired', 'revoked', 'error'
    last_sync_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (user relationship removed for device-based auth)
    execution_logs = relationship("ExecutionLog", back_populates="trading_account")
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired or expiring within 24 hours"""
        if not self.token_expires_at:
            return True
        # Consider expired if less than 24 hours remaining
        expiry_buffer = timedelta(hours=24)
        return datetime.utcnow() > (self.token_expires_at - expiry_buffer)
    
    def get_token_status(self) -> str:
        """Get human-readable token status"""
        if not self.is_connected:
            return "Not Connected"
        if self.connection_status == "revoked":
            return "Revoked by User"
        if self.connection_status == "error":
            return "Connection Error"
        if self.is_token_expired():
            return "Token Expired (Refresh Required)"
        days_left = (self.token_expires_at - datetime.utcnow()).days
        return f"Active ({days_left} days left)"
    
    def __repr__(self):
        return f"<TradingAccount(id={self.id}, broker={self.broker_name}, equity={self.account_equity})>"


class ExecutionLog(Base):
    """
    Audit trail for trade executions across all user accounts.
    
    Used for:
    - Compliance reporting
    - Debugging execution issues
    - Performance analytics per broker/account
    """
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True)
    trading_account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False)
    
    # Trade details
    strategy_name = Column(String(100))  # Which strategy triggered the trade
    action_type = Column(String(20))  # 'BUY', 'SELL', 'CLOSE'
    symbol = Column(String(20))  # e.g., 'GBPUSD', 'EURUSD'
    volume = Column(Float)  # Lot size
    execution_price = Column(Float)  # Fill price
    
    # cTrader response
    cTrader_order_id = Column(String(50))
    status = Column(String(20))  # 'pending', 'executed', 'failed', 'cancelled'
    error_message = Column(Text)
    execution_time_ms = Column(Integer)  # How long the execution took
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    trading_account = relationship("TradingAccount", back_populates="execution_logs")
    
    def __repr__(self):
        return f"<ExecutionLog(symbol={self.symbol}, action={self.action_type}, status={self.status})>"


class TokenRefreshLog(Base):
    """
    Log of OAuth token refresh attempts.
    
    cTrader access tokens expire after 30 days. This log helps monitor
    the health of automatic token refresh operations.
    """
    __tablename__ = "token_refresh_logs"
    
    id = Column(Integer, primary_key=True)
    trading_account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False)
    
    old_token_expires_at = Column(DateTime)
    new_token_expires_at = Column(DateTime)
    refresh_successful = Column(Boolean)
    error_message = Column(Text)
    refreshed_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TokenRefreshLog(success={self.refresh_successful})>"