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

    API keys for NVIDIA, brokers, and WhatsApp are configured via Settings page
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

    # NVIDIA NIM API (DEPRECATED - use Gemini 2.5 Flash instead via GEMINI_API_KEYS)
    # Kept as a fallback; the LLM service prefers Gemini when GEMINI_API_KEYS is set.
    NVIDIA_API_KEY: Optional[str] = None  # Set via Settings page
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Google Gemini 2.5 Flash - PRIMARY LLM provider (free tier, multi-key rotation)
    # IMPORTANT: Gemini rate limits are PER PROJECT, so each key below should come
    # from a SEPARATE Google account / AI Studio project to keep quotas independent.
    # Comma- or newline-separated. Get keys at https://aistudio.google.com/apikey
    GEMINI_API_KEYS: Optional[str] = None  # e.g. "key1,key2,key3,key4"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Model Routing - Gemini 2.5 Flash family (FREE tier).
    # flash-lite: fast/high-RPD (risk checks, execution, simple tasks)
    # flash: balanced analysis (news, sentiment, quant)
    # pro: deep reasoning (portfolio), used sparingly (low free-tier RPD)
    MODEL_FAST: str = "gemini-2.5-flash-lite"        # fast, ~30 RPM / 1500 RPD FREE
    MODEL_FREE_FAST: str = "gemini-2.5-flash-lite"   # same as fast (FREE verified)
    MODEL_BALANCED: str = "gemini-2.5-flash"          # ~10 RPM / 250 RPD FREE
    MODEL_SMART: str = "gemini-2.5-flash"            # analysis model
    MODEL_SMART_FREE: str = "gemini-2.5-flash"       # analysis (FREE verified)
    MODEL_DEEP: str = "gemini-2.5-pro"               # ~5 RPM / 25 RPD FREE - use sparingly
    MODEL_ALTERNATIVE: str = "gemini-2.5-flash"      # ensemble members

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

    # Kronos Integration (4GB RAM optimized)
    KRONOS_MODEL: str = "kronos-mini"  # or "kronos-mini-int8" for quantized
    KRONOS_FORECAST_HORIZON: int = 50  # Number of bars to predict
    KRONOS_BATCH_SIZE: int = 3  # Micro-batch size for 4GB RAM
    KRONOS_MEMORY_THRESHOLD: float = 85.0  # Pause inference if RAM > 85%
    KRONOS_USE_CLOUD: bool = False  # Use HuggingFace/remote fallback (Colab removed)
    HUGGINGFACE_API_TOKEN: Optional[str] = None
    # DEPRECATED: legacy key referenced by kronos/hybrid_service.py for a Colab
    # code path that is never invoked (KRONOS_USE_CLOUD=false, no Colab URL set).
    # Kept only so the module imports cleanly; remove when hybrid_service is stripped.
    KRONOS_COLAB_STRATEGY: str = "cascade"

    # Kronos Remote Service (Render Deployment)
    KRONOS_SERVICE_URL: Optional[str] = None  # Remote Kronos service URL (Render)

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

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None  # Bot token from BotFather

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
    def gemini_configured(self) -> bool:
        """True if at least one Gemini API key is configured."""
        return bool(self.GEMINI_API_KEYS)

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
        nvidia_key = get_api_key_from_settings("nvidia_api_key", settings.NVIDIA_API_KEY)
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
                    
                    if key_name == "nvidia_api_key" and device_settings.nvidia_key:
                        return encryption.decrypt(device_settings.nvidia_key)
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
