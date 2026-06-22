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

    # NVIDIA NIM API - Use database settings if available
    NVIDIA_API_KEY: Optional[str] = None  # Set via Settings page
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Model Routing - Based on actual FREE tier testing (2026-06)
    # Working FREE models: meta/llama-3.2-3b, meta/llama-3.1-8b, meta/llama-3.1-70b, meta/llama-3.3-70b, mistralai/mixtral-8x7b, nvidia/nemotron-mini-4b, moonshotai/kimi-k2.6
    # Meta/Llama models (3.2-3b, 3.1-8b, 3.1-70b, 3.3-70b) are FREE and verified ✅
    # Mistral Mixtral 8x7B is FREE and verified ✅
    # NVIDIA Nemotron 4B is FREE and verified ✅
    MODEL_FAST: str = "meta/llama-3.2-3b-instruct"  # 3B, fast, FREE verified ✅
    MODEL_FREE_FAST: str = "meta/llama-3.2-3b-instruct"  # Same as fast - confirmed FREE ✅
    MODEL_BALANCED: str = "meta/llama-3.1-8b-instruct"  # Mid-size, FREE verified ✅
    MODEL_SMART: str = "meta/llama-3.1-70b-instruct"  # 70B reasoning, FREE verified ✅
    MODEL_SMART_FREE: str = "meta/llama-3.1-70b-instruct"  # Best FREE reasoning ✅
    MODEL_DEEP: str = "meta/llama-3.3-70b-instruct"  # 70B is deepest FREE available ✅
    MODEL_ALTERNATIVE: str = "mistralai/mixtral-8x7b-instruct-v0.1"  # Alternative perspective, FREE ✅

    # Binance - Use database settings if available
    BINANCE_API_KEY: Optional[str] = None  # Set via Settings page
    BINANCE_API_SECRET: Optional[str] = None  # Set via Settings page

    # Solana/Jupiter
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    JUPITER_API_KEY: Optional[str] = None

    # Copy Trading
    GITHUB_TOKEN: Optional[str] = None

    # Security - CRITICAL: Must be changed in production
    SECRET_KEY: str = "change-this-in-production"  # Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
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
    KRONOS_USE_CLOUD: bool = False  # Use HuggingFace/Colab fallback
    HUGGINGFACE_API_TOKEN: Optional[str] = None

    # Kronos Colab Integration (3-model ensemble)
    KRONOS_COLAB_URL: Optional[str] = None  # Colab public URL (ngrok)
    KRONOS_COLAB_STRATEGY: str = "cascade"  # cascade|ensemble|context|mini|small|base

    # cTrader OpenAPI (OAuth 2.0 Copy Trading)
    CTRADER_CLIENT_ID: Optional[str] = None
    CTRADER_CLIENT_SECRET: Optional[str] = None
    CTRADER_REDIRECT_URI: Optional[str] = None
    CTRADER_SANDBOX: bool = True
    CTRADER_ENCRYPTION_KEY: Optional[str] = None
    CTRADER_BROKER_ENABLED: bool = True
    CTRADER_RATE_LIMIT: int = 50

    # WhatsApp Integration - Use database settings
    WHATSAPP_SERVICE_URL: str = "http://localhost:2785"  # Default OpenWA URL

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None  # Bot token from BotFather

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


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
                    from app.services.whatsapp_service import EncryptionService
                    encryption = EncryptionService()
                    
                    if key_name == "nvidia_api_key" and device_settings.nvidia_key:
                        return encryption.decrypt(device_settings.nvidia_key)
                    elif key_name == "binance_api_key" and device_settings.binance_key:
                        return encryption.decrypt(device_settings.binance_key)
                    elif key_name == "binance_api_secret" and device_settings.binance_secret:
                        return encryption.decrypt(device_settings.binance_secret)
                    elif key_name == "colab_kronos_url" and device_settings.colab_url:
                        return device_settings.colab_url
                
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
