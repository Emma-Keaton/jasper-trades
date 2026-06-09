# Database Models
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Trade(Base):
    """Trade execution record."""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # buy/sell
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    order_type = Column(String, default="market")
    status = Column(String, default="pending")  # pending, submitted, filled, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Broker info
    broker = Column(String)  # alpaca, binance, ibkr, solana
    broker_order_id = Column(String)
    
    # Agent info
    agent_name = Column(String)
    signal_id = Column(String)
    
    # PnL
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)


class Signal(Base):
    """Trading signal from agents."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)  # buy, sell, hold
    strength = Column(Float)  # 0-1 confidence
    agent_name = Column(String, nullable=False)
    reasoning = Column(Text)  # AI-generated explanation
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    # Signal metadata (using signal_data to avoid SQLAlchemy conflict)
    signal_data = Column(JSON)

    # Copy trading
    is_public = Column(Boolean, default=True)
    copied_by = Column(Integer, default=0)


class Portfolio(Base):
    """Portfolio holdings."""
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, default="Default")
    cash = Column(Float, default=100000.0)  # Start with $100K for paper trading
    initial_value = Column(Float, default=100000.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Type
    is_paper = Column(Boolean, default=True)
    broker = Column(String)


class Position(Base):
    """Current position in a symbol."""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    symbol = Column(String, nullable=False)
    quantity = Column(Float, default=0)
    avg_price = Column(Float, default=0)
    current_price = Column(Float)
    market_value = Column(Float)
    unrealized_pnl = Column(Float)
    unrealized_pnl_percent = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Agent(Base):
    """Registered AI agents."""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String)  # director, quant, risk, execution, specialist
    model = Column(String)  # NVIDIA NIM model to use
    is_active = Column(Boolean, default=False)
    config = Column(JSON)  # Agent-specific configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Performance tracking
    total_signals = Column(Integer, default=0)
    win_rate = Column(Float)
    total_pnl = Column(Float)


class BacktestResult(Base):
    """Backtest execution results."""
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    strategy = Column(String)
    symbol = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Results
    initial_capital = Column(Float)
    final_capital = Column(Float)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    
    # Metadata
    config = Column(JSON)
    trades = Column(JSON)  # Serialized trade history
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPreference(Base):
    """User preferences and settings."""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Memory(Base):
    """Persistent memory for agents (from Vibe-Trading)."""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True)
    session_id = Column(String)
    content = Column(Text, nullable=False)
    category = Column(String)  # user_preference, trading_rule, pattern, etc.
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeviceSettings(Base):
    """Per-device API key storage with encryption. Unified settings for brokers, notifications, and LLM."""
    __tablename__ = "device_settings"

    device_id = Column(String, primary_key=True)  # SHA256 fingerprint

    # Broker API keys (encrypted)
    nvidia_key = Column(String, nullable=True)  # Encrypted
    alpaca_key = Column(String, nullable=True)  # Encrypted
    alpaca_secret = Column(String, nullable=True)  # Encrypted
    alpaca_paper = Column(Boolean, default=True)
    binance_key = Column(String, nullable=True)  # Encrypted
    binance_secret = Column(String, nullable=True)  # Encrypted

    # IBKR (encrypted JSON)
    ibkr_host = Column(String, nullable=True)
    ibkr_port = Column(Integer, nullable=True)
    ibkr_client_id = Column(Integer, nullable=True)
    ibkr_enabled = Column(Boolean, default=False)

    # Solana/Jupiter
    solana_rpc_url = Column(String, nullable=True)
    jupiter_enabled = Column(Boolean, default=False)

    # Exness/MT5 (encrypted)
    exness_login_id = Column(String, nullable=True)  # MT5 Login ID (e.g., 87291043)
    exness_server = Column(String, nullable=True)  # MT5 Server (e.g., Exness-MT5-Real6)
    exness_password = Column(String, nullable=True)  # Encrypted trading password
    exness_investor_password = Column(String, nullable=True)  # Encrypted investor password (read-only)
    exness_enabled = Column(Boolean, default=False)

    colab_url = Column(String, nullable=True)  # Kronos Colab URL

    # Notification configs (stored as encrypted JSON strings)
    discord_config = Column(String, nullable=True)  # JSON: {webhook_url, enabled}
    slack_config = Column(String, nullable=True)  # JSON: {webhook_url, enabled}
    email_config = Column(String, nullable=True)  # JSON: {smtp_server, smtp_port, username, password, from_email, to_emails, enabled}
    telegram_config = Column(String, nullable=True)  # JSON: {bot_token, chat_id, enabled}
    whatsapp_config = Column(String, nullable=True)  # JSON: {phone_number, openwa_url, enabled, chat_enabled}

    # Market Data APIs (encrypted)
    alphavantage_key = Column(String, nullable=True)  # Encrypted
    finnhub_key = Column(String, nullable=True)  # Encrypted
    twelvedata_key = Column(String, nullable=True)  # Encrypted
    polygon_key = Column(String, nullable=True)  # Encrypted
    fred_key = Column(String, nullable=True)  # Encrypted (Federal Reserve Economic Data)
    coingecko_enabled = Column(Boolean, default=True)  # Free, no API key needed

    # News/Sentiment APIs (encrypted)
    newsapi_key = Column(String, nullable=True)  # Encrypted
    cryptopanic_key = Column(String, nullable=True)  # Encrypted
    av_news_sentiment_enabled = Column(Boolean, default=True)  # Uses Alpha Vantage key

    # Email Service (encrypted JSON)
    sendgrid_config = Column(String, nullable=True)  # JSON: {api_key, from_email, enabled}

    # Discord Bot (encrypted JSON)
    discord_bot_config = Column(String, nullable=True)  # JSON: {bot_token, guild_id, channel_id, enabled, chat_enabled}

    # LLM settings
    nvidia_model = Column(String, nullable=True, default="nvidia/nemotron-mini-4b-instruct")

    # Trading preferences
    default_brokers = Column(String, nullable=True)  # Comma-separated list of enabled brokers
    routing_mode = Column(String, nullable=True, default="asset_class")  # "all", "asset_class", "ai_decided"

    # Auto-Payout Configuration (encrypted JSON)
    # Structure: {
    #   "payout_enabled": true,
    #   "payout_percentage": 50.0,  // Configurable: 0-100
    #   "payout_schedule_hour": 20,  // 0-23 ET
    #   "payout_destination": "crypto_wallet",  // "crypto_wallet" | "forex_account" | "split"
    #   "crypto_wallet": "0x...",  // USDT wallet (ERC20 or SOLANA)
    #   "crypto_chain": "ethereum",  // "ethereum" | "solana" | "bsc"
    #   "forex_reinvest_percentage": 100.0,  // If forex: % of profit to reinvest
    #   "split_ratio": 50,  // If split: % to crypto (remainder to forex)
    #   "min_payout_threshold": 10.0  // Minimum profit before payout triggers
    # }
    payout_config = Column(String, nullable=True)  # Encrypted JSON

    # Tatum API key for blockchain transfers (encrypted)
    tatum_api_key = Column(String, nullable=True)  # Encrypted

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    """WhatsApp chat messages for conversation history."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    phone_number = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    direction = Column(String, nullable=False)  # 'incoming' or 'outgoing'
    message_type = Column(String, default='text')  # text, command, ai_response
    created_at = Column(DateTime, default=datetime.utcnow)

    # For AI context
    intent = Column(String)  # detected intent (status, positions, etc.)
    response_to_id = Column(Integer)  # ID of message this is replying to


class Withdrawal(Base):
    """Withdrawal request and execution log."""
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))

    # Amount
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")  # USD, USDC, etc.

    # Type
    withdrawal_type = Column(String, nullable=False)  # "auto_payout" or "manual"
    destination_type = Column(String)  # "crypto_wallet" or "broker"
    destination_address = Column(String)  # Wallet address or broker account

    # Status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    transaction_hash = Column(String)  # Blockchain tx hash

    # Fees
    fee = Column(Float, default=0.0)
    net_amount = Column(Float)  # amount - fee

    # PnL context (for auto-payout)
    daily_pnl = Column(Float)  # Daily PnL when auto-payout triggered
    payout_percentage = Column(Float, default=50.0)  # % of profit

    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    # Error handling
    error_message = Column(String)

    # Relationships
    portfolio = relationship("Portfolio", backref="withdrawals")


class RiskSnapshot(Base):
    """Periodic risk metrics snapshot for charts."""
    __tablename__ = "risk_snapshots"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    var_95 = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionLog(Base):
    """Decision log for cross-session learning."""
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)  # buy, sell, hold
    reasoning = Column(Text)
    confidence = Column(Float)  # 0-1
    agent_name = Column(String, default="Director")
    context = Column(JSON)  # market context at decision time
    status = Column(String, default="pending")  # pending, closed
    realized_return = Column(Float)
    reflection = Column(Text)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "action": self.action,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "agent_name": self.agent_name,
            "context": self.context,
            "status": self.status,
            "realized_return": self.realized_return,
            "reflection": self.reflection,
            "portfolio_id": self.portfolio_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ================= AI-Trader Signal System ==============

class SignalEnhanced(Base):
    """Enhanced trading signal from AI-Trader (position, strategy, discussion)."""
    __tablename__ = "signals_enhanced"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    agent_name = Column(String, nullable=False)
    
    # Signal type: 'position', 'strategy', 'discussion'
    message_type = Column(String, nullable=False)
    
    # Market and symbol
    market = Column(String)  # 'us-stock', 'crypto', 'polymarket'
    symbol = Column(String)
    
    # Position-specific fields
    action = Column(String)  # 'buy', 'sell', 'short', 'cover'
    price = Column(Float)
    quantity = Column(Float)
    side = Column(String)  # 'long', 'short'
    
    # Strategy/Discussion fields
    title = Column(String)
    content = Column(Text)
    tags = Column(String)  # Comma-separated tags
    
    # Social metrics
    reply_count = Column(Integer, default=0)
    participant_count = Column(Integer, default=0)
    is_following_author = Column(Boolean, default=False)
    
    # Metadata
    signal_data = Column(JSON)  # Additional metadata
    is_public = Column(Boolean, default=True)
    executed_at = Column(DateTime)  # Trade execution time
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subscription(Base):
    """Copy trading subscription (follower following a leader)."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    follower_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    leader_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    
    status = Column(String, default="active")  # 'active', 'paused', 'unsubscribed'
    copied_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Challenge(Base):
    """Trading challenge competition from AI-Trader."""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    challenge_key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Challenge config
    market = Column(String)  # 'crypto', 'us-stock', 'polymarket'
    track = Column(String)  # Same as market, for compatibility
    symbol = Column(String)  # Fixed symbol (optional)
    variant_key = Column(String)  # 'control', etc.
    
    # Timing
    start_at = Column(DateTime)
    end_at = Column(DateTime)
    status = Column(String, default="upcoming")  # 'upcoming', 'active', 'settled'
    
    # Scoring
    scoring_method = Column(String, default="return_pct")  # 'return_pct', 'sharpe', etc.
    starting_cash = Column(Float, default=1000.0)
    
    # Rules
    max_position_size = Column(Float)
    max_drawdown = Column(Float)
    
    # Metadata
    rules = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChallengeParticipant(Base):
    """Agent participating in a challenge."""
    __tablename__ = "challenge_participants"

    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    
    # Performance
    return_pct = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    risk_adjusted_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    trade_count = Column(Integer, default=0)
    
    # Status
    rank = Column(Integer)
    disqualified_reason = Column(String)
    
    # Cash and equity
    starting_cash = Column(Float, default=1000.0)
    current_cash = Column(Float, default=1000.0)
    portfolio_value = Column(Float, default=1000.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChallengeTrade(Base):
    """Trade within a challenge (isolated from normal trades)."""
    __tablename__ = "challenge_trades"

    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("challenge_participants.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)

    # Trade details
    side = Column(String, nullable=False)  # 'buy', 'sell', 'short', 'cover'
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    content = Column(Text)  # Trade note

    # Challenge portfolio impact
    cash_before = Column(Float)
    cash_after = Column(Float)

    executed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class Follow(Base):
    """Copy trading: User follows a trader/agent."""
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    leader_id = Column(String, nullable=False)  # Agent name or trader ID
    leader_type = Column(String, default="agent")  # 'agent' or 'human'
    
    # Copy settings
    copy_percentage = Column(Float, default=100.0)  # 0-100%
    max_position_size = Column(Float, default=10000.0)  # Max position in $
    auto_copy = Column(Boolean, default=True)
    
    # Status
    active = Column(Boolean, default=True)
    paused_at = Column(DateTime, nullable=True)
    
    # Stats
    signals_copied = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    
    followed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CopyTrade(Base):
    """Record of a copied trade."""
    __tablename__ = "copy_trades"

    id = Column(Integer, primary_key=True)
    follow_id = Column(Integer, ForeignKey("follows.id"), nullable=False)
    original_signal_id = Column(Integer, ForeignKey("signals.id"), nullable=False)
    resulting_trade_id = Column(Integer, ForeignKey("trades.id"), nullable=True)

    # Copy details
    copy_percentage = Column(Float, nullable=False)
    original_quantity = Column(Float, nullable=False)
    copied_quantity = Column(Float, nullable=False)

    # PnL tracking
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)

    copied_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TradingCap(Base):
    """Trading caps/risk limits per portfolio to prevent over-exposure."""
    __tablename__ = "trading_caps"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)

    # Risk limits
    max_position_amount = Column(Float, nullable=True)  # Max $ per trade (e.g., $5,000)
    max_position_percentage = Column(Float, nullable=True)  # Max % of portfolio (e.g., 20.0)
    daily_loss_limit = Column(Float, nullable=True)  # Max daily loss in $ (e.g., $2,000)
    daily_loss_percentage = Column(Float, nullable=True)  # Max daily loss % (e.g., 5.0)

    # Enforcement
    hard_limit = Column(Boolean, default=True)  # If True, block trades that exceed caps
    soft_limit_enabled = Column(Boolean, default=False)  # If True, warn but allow

    # Status
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", backref="trading_caps")


class BrokerAccount(Base):
    """Linked external broker account (Exness, MT5, etc.)."""
    __tablename__ = "broker_accounts"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)

    # Broker type
    broker_type = Column(String, nullable=False)  # 'exness', 'alpaca', 'binance', etc.
    broker_name = Column(String)  # Display name (e.g., "Exness Real-6")

    # Account credentials (encrypted)
    account_id = Column(String, nullable=False)  # MT5 Login ID or broker account ID
    account_password = Column(String, nullable=True)  # Encrypted trading password
    investor_password = Column(String, nullable=True)  # Encrypted investor password (read-only)
    server_name = Column(String, nullable=True)  # MT5 server (e.g., "Exness-MT5-Real6")

    # Connection status
    is_connected = Column(Boolean, default=False)
    last_sync_at = Column(DateTime, nullable=True)
    connection_error = Column(String, nullable=True)

    # Account info (cached from broker)
    balance = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    margin = Column(Float, default=0.0)
    free_margin = Column(Float, default=0.0)
    currency = Column(String, default="USD")

    # Metadata
    config = Column(JSON)  # Broker-specific config
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", backref="broker_accounts")
