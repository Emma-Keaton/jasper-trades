"""
Polymarket CLOB Account Models

AI-driven prediction market trading with encrypted API credentials.
Authentication: Device ID fingerprint via localStorage (no user accounts)

Features:
- Encrypted API key/secret storage (Fernet/AES-128)
- AI copytrading of top Polymarket leaders
- Direct AI trading on prediction markets
- Position tracking and PnL analytics
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
from database import Base


class PolymarketAccount(Base):
    """
    Device's Polymarket CLOB account with API credentials.

    Security: API key/secret are encrypted at rest using Fernet encryption.
    The encryption key must be set via POLYMARKET_ENCRYPTION_KEY environment variable.

    AI Trading: This account can be used by AI agents to:
    1. Execute direct trades based on market analysis
    2. Copytrade top Polymarket leaders automatically
    """
    __tablename__ = "polymarket_accounts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), nullable=False, index=True)  # Device fingerprint

    # Encrypted API credentials (NEVER store in plaintext!)
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)

    # Account metadata from Polymarket CLOB
    wallet_address = Column(String(50))  # Public wallet address
    account_currency = Column(String(3), default="USD")
    account_balance = Column(Float, default=0.0)
    account_equity = Column(Float, default=0.0)

    # AI Trading Configuration
    ai_trading_enabled = Column(Boolean, default=False)  # Allow AI to trade this account
    copytrading_enabled = Column(Boolean, default=False)  # Enable copytrading leaders
    max_position_size = Column(Float, default=100.0)  # Max USD per trade
    max_portfolio_risk = Column(Float, default=0.20)  # Max 20% of portfolio at risk

    # Status flags
    is_active = Column(Boolean, default=True)
    is_connected = Column(Boolean, default=False)  # API connection status
    connection_status = Column(String(50))  # 'connected', 'invalid_keys', 'api_error'
    last_balance_sync_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_trade_at = Column(DateTime)

    # Relationships
    polymarket_positions = relationship("PolymarketPosition", back_populates="account")
    polymarket_trades = relationship("PolymarketTrade", back_populates="account")
    polymarket_leader_configs = relationship("PolymarketLeaderConfig", back_populates="account")

    def __repr__(self):
        return f"<PolymarketAccount(wallet={self.wallet_address}, balance={self.account_balance})>"


class PolymarketLeaderConfig(Base):
    """
    Configuration for which Polymarket leaders to copytrade.

    Users can follow multiple leaders with different allocation weights.
    AI monitors leader performance and adjusts allocations dynamically.
    """
    __tablename__ = "polymarket_leader_configs"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("polymarket_accounts.id"), nullable=False)

    # Leader identification
    leader_id = Column(String(100), nullable=False)  # Polymarket user ID
    leader_name = Column(String(100))  # Display name
    leader_wallet = Column(String(50))  # Public wallet for tracking

    # Copytrading config
    allocation_weight = Column(Float, default=0.5)  # 0.0-1.0: how much to allocate to this leader
    min_confidence = Column(Float, default=0.7)  # Only copy trades above this confidence
    max_copy_amount = Column(Float, default=50.0)  # Max USD per copied trade

    # Performance tracking
    total_copied_trades = Column(Integer, default=0)
    successful_copies = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)

    # Status
    is_active = Column(Boolean, default=True)  # User can pause copying
    last_copy_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("PolymarketAccount", back_populates="polymarket_leader_configs")

    def __repr__(self):
        return f"<PolymarketLeaderConfig(leader={ self.leader_name}, weight={self.allocation_weight})>"


class PolymarketPosition(Base):
    """
    Open Polymarket position (outcome tokens held).

    Tracked for portfolio analytics and AI risk management.
    """
    __tablename__ = "polymarket_positions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("polymarket_accounts.id"), nullable=False)

    # Market info
    market_id = Column(String(100), nullable=False)
    market_question = Column(String(500))
    market_slug = Column(String(200))

    # Position details
    outcome = Column(String(100), nullable=False)  # e.g., "Yes", "No"
    token_id = Column(String(50))  # CLOB token ID
    quantity = Column(Float, nullable=False)  # Number of outcome tokens
    average_entry_price = Column(Float, nullable=False)  # Avg price paid per token

    # Current state
    current_price = Column(Float, default=0.0)  # Current market price
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percent = Column(Float, default=0.0)

    # Trade metadata
    opened_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime)

    # Relationships
    account = relationship("PolymarketAccount", back_populates="polymarket_positions")

    def __repr__(self):
        return f"<PolymarketPosition(market={self.market_question[:30]}, outcome={self.outcome}, qty={self.quantity})>"


class PolymarketTrade(Base):
    """
    Historical Polymarket trade (filled orders).

    Used for:
    - Copytrading analytics (which leaders to follow)
    - AI performance tracking
    - Tax/compliance reporting
    """
    __tablename__ = "polymarket_trades"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("polymarket_accounts.id"), nullable=False)

    # Trade details
    market_id = Column(String(100), nullable=False)
    market_question = Column(String(500))
    outcome = Column(String(100), nullable=False)

    # Order info
    side = Column(String(10), nullable=False)  # 'BUY' or 'SELL'
    quantity = Column(Float, nullable=False)
    execution_price = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)  # quantity * price

    # Execution metadata
    clob_order_id = Column(String(100))
    clob_trade_id = Column(String(100))
    execution_timestamp = Column(DateTime)

    # Trade context
    was_copytrade = Column(Boolean, default=False)  # Was this a copied leader trade?
    copied_from_leader_id = Column(String(100))  # If copytrade, which leader?
    ai_agent_decision = Column(String(50))  # Which AI agent made the decision?

    # PnL (for SELL trades)
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_percent = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    account = relationship("PolymarketAccount", back_populates="polymarket_trades")

    def __repr__(self):
        return f"<PolymarketTrade(market={self.market_question[:30]}, side={self.side}, pnl={self.realized_pnl})>"