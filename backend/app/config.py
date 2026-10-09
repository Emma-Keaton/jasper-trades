# Configuration
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import structlog
import os

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables + database.

    Priority:
    1. Settings from database (loaded via Settings API)
    2. Environment variables
    3. Default values

    API keys for brokers and WhatsApp are configured via Settings page
    and stored encrypted in the database. Environment variables are fallback.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Allow extra fields from .env that aren't in the model
    )

    # Application
    APP_NAME: str = "Jasper Trades"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))  # Render sets PORT=8080

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"
    DATA_DIR: str = "./data"

    # Supabase (Postgres-backed persistence; survives redeploys)
    # Set DATABASE_URL to your Supabase pooler connection string, e.g.
    #   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
    # and the keys below for optional realtime/auth/storage clients.
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # Groq - PRIMARY LLM provider (free tier, multi-key rotation)
    # Comma- or newline-separated keys. Get keys at https://console.groq.com/keys
    GROQ_API_KEY: Optional[str] = None  # e.g. "key1,key2,key3"
    GROQ_API_KEYS: Optional[str] = None  # deprecated alias
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Model Routing (Groq free tier).
    # qwen3.8-27b: fast/small (risk checks, execution, simple tasks)
    # gpt-oss-120b: analysis/deep reasoning
    MODEL_FAST: str = "qwen/qwen3.8-27b"
    MODEL_FREE_FAST: str = "qwen/qwen3.8-27b"
    MODEL_BALANCED: str = "openai/gpt-oss-120b"
    MODEL_SMART: str = "openai/gpt-oss-120b"
    MODEL_SMART_FREE: str = "openai/gpt-oss-120b"
    MODEL_DEEP: str = "openai/gpt-oss-120b"
    MODEL_ALTERNATIVE: str = "openai/gpt-oss-20b"

    # Binance - Use database settings if available
    BINANCE_API_KEY: Optional[str] = None  # Set via Settings page
    BINANCE_API_SECRET: Optional[str] = None  # Set via Settings page
    FINNHUB_API_KEY: Optional[str] = None  # Set via Settings page
    ALPHAVANTAGE_API_KEY: Optional[str] = None  # Set via Settings page

    # Solana/Jupiter
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    JUPITER_API_KEY: Optional[str] = None

    # CCXT market data + live crypto (Nigeria-accessible CEX set, geo-probe gated)
    # Comma-separated exchange IDs; the geo-probe prunes to whatever works.
    CCXT_EXCHANGES: str = "bybit,okx,kucoin,gate,htx,bingx,bitget,mexc,kraken,coinbase,bitfinex,bitstamp"
    CCXT_BINANCE_OPT_IN: bool = False  # Binance only if its public market-data API works from the region

    # Solana memecoin market data (DexScreener discovery + Jupiter execution)
    DEXSCREENER_API: str = "https://api.dexscreener.com"
    JUPITER_LITE_API: str = "https://lite-api.jup.ag"

    # CoinMarketCap market data (top movers, quotes, listings). Optional.
    CMC_API_KEY: Optional[str] = None  # pro-api.coinmarketcap.com key

    # Copy Trading
    GITHUB_TOKEN: Optional[str] = None

    # WalletConnect project ID (served to frontend via public settings endpoint)
    WALLETCONNECT_PROJECT_ID: Optional[str] = None

    # Security - CRITICAL: Must be changed in production
    SECRET_KEY: str = "change-this-in-production"  # Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"
    API_AUTH_KEY: str = "jasper-auth-key-change-me"  # Generate secure random key for production
    
    # Environment
    ENVIRONMENT: str = "development"  # "development" | "production"
    
    # Rate Limiting (Production Security)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100
    
    # Security Headers
    SECURITY_HSTS_ENABLED: bool = True
    SECURE_COOKIES: bool = True
    CORS_ALLOW_CREDENTIALS: bool = True  # Allow credentials in CORS (but validate origins)
    CSRF_PROTECTION_ENABLED: bool = False  # Enable when frontend implements CSRF tokens

    # CORS - Frontend URLs
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Optional third-party dependencies (app/services/optional_deps.py).
    #
    # On by default. The install is deliberately deferred: it runs after the app is
    # already serving and only once the process is under OPTIONAL_DEPS_MAX_RSS_MB,
    # so it cannot compete with boot for the 512 MB a Render free-tier instance has.
    #
    # Only affects the soft tier (statsmodels, yfinance). pandas is NOT here: it is
    # imported unguarded by 457 files and is a hard requirement declared in
    # requirements.txt.
    OPTIONAL_DEPS_AUTO_INSTALL: bool = True

    # RSS ceiling, in MB, that must be clear before the install starts. Boot peaks
    # around 190-250 MB on Render free, so 320 leaves room for one pip subprocess
    # plus its wheel extraction without risking the OOM killer mid-install.
    OPTIONAL_DEPS_MAX_RSS_MB: float = 320.0

    # Give up waiting for headroom after this long and install anyway. An install
    # that never starts because the process happens to be busy is worse than one
    # that runs at slightly higher memory.
    OPTIONAL_DEPS_MEMORY_TIMEOUT_SECONDS: float = 300.0

    # Quiet period after startup before the first memory check, so the install does
    # not begin while boot and warm-up are still competing for memory.
    OPTIONAL_DEPS_SETTLE_SECONDS: float = 20.0

    # Kronos prediction service (modal-kronos).
    # The model runs remotely; this backend owns market data and calibration.
    KRONOS_SERVICE_URL: Optional[str] = None  # e.g. https://modal-kronos--web-xxx.modal.run
    KRONOS_API_KEY: Optional[str] = None  # shared secret, sent as X-API-Key
    KRONOS_FORECAST_HORIZON: int = 50  # Number of bars to predict
    KRONOS_SAMPLES: int = 10  # sampled paths; <2 is not a distribution
    # The memory/RAM knobs below applied to an in-process torch model that this
    # backend no longer runs. Inference happens on the modal-kronos service.
    KRONOS_MODEL: str = "NeoQuasar/Kronos-mini"
    HUGGINGFACE_API_TOKEN: Optional[str] = None

    # Replacement forecasting (used when Kronos is unavailable/not configured)
    REDIS_URL: Optional[str] = None  # Optional forecast cache; falls back to in-memory
    FORECAST_CACHE_TTL: int = 900  # seconds (15 min)
    FORECAST_MIN_CANDLES: int = 50  # below this, confidence is marked reduced

    # cTrader OpenAPI (OAuth 2.0 Copy Trading)
    CTRADER_CLIENT_ID: Optional[str] = None
    CTRADER_CLIENT_SECRET: Optional[str] = None
    CTRADER_REDIRECT_URI: Optional[str] = None
    CTRADER_ENCRYPTION_KEY: Optional[str] = None
    CTRADER_BROKER_ENABLED: bool = True
    CTRADER_RATE_LIMIT: int = 50

    # Universal Paper Trading (replaces broker-specific sandbox modes)
    UNIVERSAL_PAPER_TRADING: bool = True
    UNIVERSAL_PAPER_CAPITAL: float = 10000.0
    UNIVERSAL_PAPER_CURRENCY: str = "USD"

    # Auto-payouts are DISABLED by default (safe-by-default).
    # Requires BOTH environment=production AND this flag to run the scheduler.
    AUTO_PAYOUTS_ENABLED: bool = False

    # Alpha Zoo factor trading (scheduled hands-free signals from the watchlist)
    FACTOR_TRADING_ENABLED: bool = True
    FACTOR_SWEEP_INTERVAL: int = 300  # seconds between factor sweeps
    FACTOR_TIMEFRAME: str = "1h"
    FACTOR_LIMIT_BARS: int = 300  # OHLCV bars per symbol per sweep
    FACTOR_REFRACTORY_MINUTES: int = 360  # don't re-trade the same device/symbol/side within this window

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None  # Bot token from BotFather
    # Secret token that Telegram sends in X-Telegram-Bot-Api-Secret-Token on
    # webhook calls. Verify sender authenticity in production.
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    # Agent Reach - Market Intelligence (optional, legacy shim)
    AGENT_REACH_ENABLED: bool = True  # Enable market intelligence
    AGENT_REACH_CHANNELS: str = "telegram,reddit"  # Polled via signal_sources scrapers (telegram/reddit/rss/stocktwits)
    NEWS_POLL_INTERVAL: int = 30  # 30 seconds - ultra-fast for trending stock detection
    SENTIMENT_CACHE_TTL: int = 60  # 1 minute cache for freshness
    SENTIMENT_ANALYSIS_ENABLED: bool = True  # Enable sentiment analysis

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Convenience flags indicating if API keys are configured (env or DB)
    @property
    def finnhub_configured(self) -> bool:
        return bool(self.FINNHUB_API_KEY)

    @property
    def alphavantage_configured(self) -> bool:
        return bool(self.ALPHAVANTAGE_API_KEY)

    @property
    def binance_configured(self) -> bool:
        return bool(self.BINANCE_API_KEY)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_keys)

    @property
    def groq_keys(self) -> List[str]:
        raw = self.GROQ_API_KEY or self.GROQ_API_KEYS
        keys: List[str] = []
        if raw:
            for part in str(raw).replace("\n", ",").split(","):
                k = part.strip()
                if k:
                    keys.append(k)
        return keys

    @property
    def supabase_configured(self) -> bool:
        """True if Supabase project URL + service role key are configured."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)

    @property
    def using_postgres(self) -> bool:
        """True if the configured database is Postgres/Supabase (not SQLite)."""
        return (self.DATABASE_URL or "").startswith(("postgres://", "postgresql://"))


settings = Settings()


def get_api_key_from_settings(key_name: str, fallback: Optional[str] = None) -> Optional[str]:
    """
    Get API key from database settings with fallback to environment variables.
    
    This allows users to configure API keys via Settings page instead of .env files.
    Priority:
    1. Database settings (encrypted)
    2. Environment variables
    3. Fallback value
    
        Usage:
            groq_key = get_api_key_from_settings("groq_api_key", settings.GROQ_API_KEY)
    """
    # Try to load from database first
    try:
        import asyncio
        from app.database import async_session
        from app.models import DeviceSettings
        from sqlalchemy import select
        
        async def fetch_key():
            async with async_session() as session:
                result = await session.execute(
                    select(DeviceSettings).limit(1)
                )
                device_settings = result.scalar_one_or_none()
                
                if device_settings:
                    from app.services.encryption import EncryptionHelper
                    encryption = EncryptionHelper()
                    
                    if key_name == "groq_api_key" and device_settings.groq_key:
                        return encryption.decrypt(device_settings.groq_key)
                    elif key_name == "binance_api_key" and device_settings.binance_key:
                        return encryption.decrypt(device_settings.binance_key)
                    elif key_name == "binance_api_secret" and device_settings.binance_secret:
                        return encryption.decrypt(device_settings.binance_secret)
                
                return None
        
        # Run async function
        key = asyncio.new_event_loop().run_until_complete(fetch_key())
        if key:
            logger.debug(f"Loaded {key_name} from database settings")
            return key
            
    except Exception as e:
        logger.debug(f"Could not load {key_name} from database: {e}")
        pass
    
    # Fallback to environment variable
    if fallback:
        logger.debug(f"Using fallback for {key_name} from environment")
        return fallback
    
    return None
