"""
Settings API - Unified in-app configuration with encryption
Handles brokers, notifications, LLM settings, and trading preferences.
Keys are encrypted before storage in database.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, List, Any
import hashlib
import structlog
import json
from pathlib import Path
from datetime import datetime

logger = structlog.get_logger(__name__)

# Import encryption and database
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed - keys will not be encrypted")

from app.database import async_session
from sqlalchemy import select
from app.models import DeviceSettings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ============ Request Models ============

class BrokerConfig(BaseModel):
    """Broker configuration"""
    api_key: str
    api_secret: Optional[str] = None
    paper_trading: bool = True
    enabled: bool = True


class NotificationChannel(BaseModel):
    """Notification channel config"""
    enabled: bool = True
    config: Dict[str, Any] = {}


class ApiKeySettings(BaseModel):
    """API key settings from frontend"""
    nvidia_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_paper: bool = True
    binance_api_key: str = ""
    binance_api_secret: str = ""
    colab_kronos_url: str = ""
    # IBKR
    ibkr_host: Optional[str] = None
    ibkr_port: Optional[int] = None
    ibkr_client_id: Optional[int] = None
    ibkr_enabled: bool = False
    # Solana
    solana_rpc_url: Optional[str] = None
    jupiter_enabled: bool = False


class DiscordConfig(BaseModel):
    webhook_url: str
    enabled: bool = True


class SlackConfig(BaseModel):
    webhook_url: str
    enabled: bool = True


class EmailConfig(BaseModel):
    smtp_server: str
    smtp_port: int = 587
    username: str
    password: str
    from_email: EmailStr
    to_emails: List[EmailStr]
    enabled: bool = True


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str
    enabled: bool = True


class WhatsAppConfig(BaseModel):
    phone_number: str
    openwa_url: str = "http://localhost:3001"
    enabled: bool = True
    chat_enabled: bool = True


class ValidateKeyRequest(BaseModel):
    """Validate API key request."""
    key_type: str  # "alpaca", "binance", etc.
    api_key: str
    api_secret: Optional[str] = None


class PayoutConfigRequest(BaseModel):
    """Auto-payout configuration request."""
    payout_config: Dict[str, Any] = {
        "payout_enabled": False,
        "payout_percentage": 50.0,
        "payout_schedule_hour": 20,
        "payout_destination": "crypto_wallet",
        "crypto_wallet": "",
        "crypto_chain": "ethereum",
        "split_ratio": 50,
        "min_payout_threshold": 10.0,
    }


class PayoutTestRequest(BaseModel):
    """Test payout request."""
    portfolio_id: int


class TradingPreferences(BaseModel):
    """Trading preferences"""
    default_brokers: Optional[str] = None  # Comma-separated
    routing_mode: str = "asset_class"  # "all", "asset_class", "ai_decided"


# ============ Encryption Service ============

class EncryptionService:
    """Encrypt API keys before storing in database"""

    def __init__(self):
        self.key: Optional[bytes] = None
        self.cipher: Optional[Fernet] = None
        self._init_key()

    def _init_key(self):
        """Load or create encryption key"""
        if not CRYPTO_AVAILABLE:
            return

        key_path = Path("data/encryption.key")

        if key_path.exists():
            with open(key_path, 'rb') as f:
                self.key = f.read()
        else:
            # Generate new key
            self.key = Fernet.generate_key()
            key_path.parent.mkdir(exist_ok=True)
            with open(key_path, 'wb') as f:
                f.write(self.key)
            logger.info("Generated new encryption key")

        self.cipher = Fernet(self.key)

    def encrypt(self, value: str) -> Optional[str]:
        if not self.cipher or not value:
            return value
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> Optional[str]:
        if not self.cipher or not value:
            return value
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return value

    def encrypt_json(self, data: Dict) -> Optional[str]:
        """Encrypt JSON config"""
        if not self.cipher or not data:
            return json.dumps(data) if data else None
        json_str = json.dumps(data)
        return self.cipher.encrypt(json_str.encode()).decode()

    def decrypt_json(self, value: str) -> Optional[Dict]:
        """Decrypt JSON config"""
        if not self.cipher or not value:
            return json.loads(value) if value else None
        try:
            decrypted = self.cipher.decrypt(value.encode()).decode()
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"JSON decryption failed: {e}")
            # Fallback: try as plain JSON
            try:
                return json.loads(value)
            except:
                return None


encryption = EncryptionService()


# ============ Helper Functions ============

def get_device_id(user_agent: str = Header(None, alias="User-Agent")) -> str:
    """Generate device fingerprint from User-Agent"""
    ua_string = user_agent or "unknown_device"
    fingerprint = hashlib.sha256(ua_string.encode()).hexdigest()[:16]
    return fingerprint


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask secret for display"""
    if not secret or len(secret) <= visible_chars:
        return "***"
    return secret[:visible_chars] + "***"


# ============ Main Settings Endpoints ============

@router.get("")
async def get_settings(device_id: str = Header(None, alias="X-Device-ID")):
    """
    Get all settings for current device.
    Keys are returned decrypted.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    try:
        async with async_session() as session:
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

        if not row:
            return {
                "configured": False,
                "device_id": device_id,
                "message": "No settings found. Configure your API keys below."
            }

        # Decrypt and return all settings
        return {
            "configured": True,
            "device_id": device_id,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            
            # Broker API keys (decrypted)
            "nvidia_api_key": encryption.decrypt(row.nvidia_key) if row.nvidia_key else "",
            "alpaca_api_key": encryption.decrypt(row.alpaca_key) if row.alpaca_key else "",
            "alpaca_api_secret": encryption.decrypt(row.alpaca_secret) if row.alpaca_secret else "",
            "alpaca_paper": row.alpaca_paper or True,
            "binance_api_key": encryption.decrypt(row.binance_key) if row.binance_key else "",
            "binance_secret": encryption.decrypt(row.binance_secret) if row.binance_secret else "",
            "colab_kronos_url": row.colab_url or "",
            
            # IBKR
            "ibkr_host": row.ibkr_host or "",
            "ibkr_port": row.ibkr_port,
            "ibkr_client_id": row.ibkr_client_id,
            "ibkr_enabled": row.ibkr_enabled or False,
            
            # Solana
            "solana_rpc_url": row.solana_rpc_url or "",
            "jupiter_enabled": row.jupiter_enabled or False,
            
            # Notification configs (decrypted JSON)
            "discord_config": encryption.decrypt_json(row.discord_config),
            "slack_config": encryption.decrypt_json(row.slack_config),
            "email_config": encryption.decrypt_json(row.email_config),
            "telegram_config": encryption.decrypt_json(row.telegram_config),
            "whatsapp_config": encryption.decrypt_json(row.whatsapp_config),
            
            # LLM settings
            "nvidia_model": row.nvidia_model or "nvidia/nemotron-mini-4b-instruct",
            
            # Trading preferences
            "default_brokers": row.default_brokers,
            "routing_mode": row.routing_mode or "asset_class",
        }

    except Exception as e:
        logger.error(f"Failed to get settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve settings")


@router.post("")
async def save_settings(
    settings: ApiKeySettings,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """
    Save API keys for current device.
    Keys are encrypted before storage.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    try:
        async with async_session() as session:
            # Check if exists
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if row:
                # Update existing
                row.nvidia_key = encryption.encrypt(settings.nvidia_api_key) if settings.nvidia_api_key else None
                row.alpaca_key = encryption.encrypt(settings.alpaca_api_key) if settings.alpaca_api_key else None
                row.alpaca_secret = encryption.encrypt(settings.alpaca_api_secret) if settings.alpaca_api_secret else None
                row.alpaca_paper = settings.alpaca_paper
                row.binance_key = encryption.encrypt(settings.binance_api_key) if settings.binance_api_key else None
                row.binance_secret = encryption.encrypt(settings.binance_secret) if settings.binance_secret else None
                row.colab_url = settings.colab_kronos_url
                row.updated_at = datetime.utcnow()
            else:
                # Create new
                row = DeviceSettings(
                    device_id=device_id,
                    nvidia_key=encryption.encrypt(settings.nvidia_api_key) if settings.nvidia_api_key else None,
                    alpaca_key=encryption.encrypt(settings.alpaca_api_key) if settings.alpaca_api_key else None,
                    alpaca_secret=encryption.encrypt(settings.alpaca_api_secret) if settings.alpaca_api_secret else None,
                    alpaca_paper=settings.alpaca_paper,
                    binance_key=encryption.encrypt(settings.binance_api_key) if settings.binance_api_key else None,
                    binance_secret=encryption.encrypt(settings.binance_secret) if settings.binance_secret else None,
                    colab_url=settings.colab_kronos_url,
                )
                session.add(row)

            await session.commit()
            logger.info(f"Settings saved for device {device_id}")

        return {
            "success": True,
            "device_id": device_id,
            "message": "Settings saved successfully"
        }

    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings")


@router.post("/validate-key")
async def validate_api_key(request: ValidateKeyRequest):
    """
    Test if an API key is valid (basic validation, no actual API call).
    For full validation, each service should implement their own check.
    """
    if not request.key or len(request.key) < 10:
        return {"valid": False, "message": "Key too short"}

    # Basic format validation
    if request.service == "nvidia":
        # NVIDIA keys can be various formats
        valid = request.key.startswith("nvapi-") or len(request.key) >= 20
        message = "Valid format" if valid else "Invalid NVIDIA key format"
        return {"valid": valid, "message": message}

    elif request.service == "alpaca":
        valid = request.key.startswith("PK") or len(request.key) >= 20
        message = "Valid format" if valid else "Invalid Alpaca key format (should start with PK)"
        return {"valid": valid, "message": message}

    elif request.service == "binance":
        valid = len(request.key) >= 30
        message = "Valid format" if valid else "Invalid Binance key format"
        return {"valid": valid, "message": message}

    return {"valid": True, "message": "Format OK - test connection to verify"}


# ============ Broker Settings ============

@router.get("/brokers")
async def get_broker_settings(device_id: str = Header(None, alias="X-Device-ID")):
    """Get all broker configurations"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    if not row:
        return {
            "brokers": {},
            "available": ["alpaca", "binance", "ibkr", "solana"],
        }

    # Return config without exposing secrets
    return {
        "brokers": {
            "alpaca": {
                "configured": bool(row.alpaca_key),
                "paper_trading": row.alpaca_paper or True,
                "enabled": bool(row.alpaca_key),
            },
            "binance": {
                "configured": bool(row.binance_key),
                "enabled": bool(row.binance_key),
            },
            "ibkr": {
                "configured": bool(row.ibkr_host),
                "enabled": row.ibkr_enabled or False,
                "host": row.ibkr_host,
                "port": row.ibkr_port,
            },
            "solana": {
                "configured": bool(row.solana_rpc_url),
                "enabled": row.jupiter_enabled or False,
            },
        },
        "available": ["alpaca", "binance", "ibkr", "solana"],
        "routing_mode": row.routing_mode or "asset_class",
    }


@router.post("/brokers/{broker_name}/configure")
async def configure_broker(
    broker_name: str,
    config: BrokerConfig = None,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """
    Configure a broker.
    
    **Supported brokers:**
    - alpaca (stocks, options, crypto)
    - binance (crypto)
    - ibkr (stocks, options, futures, forex)
    - solana (Solana tokens)
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        # Update broker-specific fields
        if broker_name == "alpaca":
            row.alpaca_key = encryption.encrypt(config.api_key) if config.api_key else None
            row.alpaca_secret = encryption.encrypt(config.api_secret) if config.api_secret and encryption else config.api_secret
            row.alpaca_paper = config.paper_trading
        elif broker_name == "binance":
            row.binance_key = encryption.encrypt(config.api_key) if config.api_key else None
            row.binance_secret = encryption.encrypt(config.api_secret) if config.api_secret and encryption else config.api_secret
        elif broker_name == "ibkr":
            row.ibkr_host = config.api_key  # Reuse fields for IBKR
            row.ibkr_port = int(config.api_secret) if config.api_secret else 7497
            row.ibkr_client_id = 1
            row.ibkr_enabled = config.enabled

        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info(f"Broker {broker_name} configured")
    return {"status": "configured", "broker": broker_name}


@router.post("/brokers/{broker_name}/test")
async def test_broker_connection(broker_name: str, device_id: str = Header(None, alias="X-Device-ID")):
    """Test broker connection"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Device settings not found")

    # Get decrypted keys
    alpaca_key = encryption.decrypt(row.alpaca_key) if row.alpaca_key else ""
    alpaca_secret = encryption.decrypt(row.alpaca_secret) if row.alpaca_secret else ""
    binance_key = encryption.decrypt(row.binance_key) if row.binance_key else ""
    binance_secret = encryption.decrypt(row.binance_secret) if row.binance_secret else ""

    # Test connection based on broker
    broker_config = None
    if broker_name == "alpaca":
        broker_config = {
            "api_key": alpaca_key,
            "api_secret": alpaca_secret,
            "paper": row.alpaca_paper,
        }
    elif broker_name == "binance":
        broker_config = {
            "api_key": binance_key,
            "api_secret": binance_secret,
        }

    if not broker_config:
        return {"status": "skipped", "broker": broker_name, "message": "Test not implemented"}

    # Import and test broker
    try:
        from app.brokers.alpaca_service import AlpacaBrokerService
        from app.brokers.ccxt_service import CCXTBrokerService
        
        broker_service = None
        if broker_name == "alpaca":
            broker_service = AlpacaBrokerService(config=broker_config)
        elif broker_name == "binance":
            broker_service = CCXTBrokerService(exchange_id="binance", config=broker_config)
        
        connected = await broker_service.connect()

        if connected:
            try:
                account = await broker_service.get_account_data()
                return {
                    "status": "connected",
                    "broker": broker_name,
                    "account_value": account.get("equity", "N/A") if account else "N/A",
                    "cash": account.get("cash", "N/A") if account else "N/A",
                }
            except:
                return {
                    "status": "connected",
                    "broker": broker_name,
                    "message": "Connected (account data unavailable)",
                }
        else:
            return {
                "status": "failed",
                "broker": broker_name,
                "error": "Connection failed",
            }

    except Exception as e:
        return {
            "status": "error",
            "broker": broker_name,
            "error": str(e),
        }


# ============ Notification Settings ============

@router.get("/notifications")
async def get_notification_settings(device_id: str = Header(None, alias="X-Device-ID")):
    """Get all notification channel configurations"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    if not row:
        return {
            "channels": {
                "discord": {"configured": False, "enabled": False},
                "slack": {"configured": False, "enabled": False},
                "email": {"configured": False, "enabled": False},
                "telegram": {"configured": False, "enabled": False},
                "whatsapp": {"configured": False, "enabled": False, "chat_enabled": False},
            }
        }

    # Decrypt and return channel configs
    return {
        "channels": {
            "discord": encryption.decrypt_json(row.discord_config) or {"configured": False, "enabled": False},
            "slack": encryption.decrypt_json(row.slack_config) or {"configured": False, "enabled": False},
            "email": encryption.decrypt_json(row.email_config) or {"configured": False, "enabled": False},
            "telegram": encryption.decrypt_json(row.telegram_config) or {"configured": False, "enabled": False},
            "whatsapp": encryption.decrypt_json(row.whatsapp_config) or {"configured": False, "enabled": False, "chat_enabled": False},
        }
    }


@router.post("/notifications/discord/configure")
async def configure_discord(
    config: DiscordConfig,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """Configure Discord webhook"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        config_dict = {"webhook_url": config.webhook_url, "enabled": config.enabled}
        row.discord_config = encryption.encrypt_json(config_dict)
        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info("Discord notifications configured")
    return {"status": "configured", "channel": "discord"}


@router.post("/notifications/slack/configure")
async def configure_slack(
    config: SlackConfig,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """Configure Slack webhook"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        config_dict = {"webhook_url": config.webhook_url, "enabled": config.enabled}
        row.slack_config = encryption.encrypt_json(config_dict)
        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info("Slack notifications configured")
    return {"status": "configured", "channel": "slack"}


@router.post("/notifications/email/configure")
async def configure_email(
    config: EmailConfig,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """Configure Email SMTP"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        config_dict = {
            "smtp_server": config.smtp_server,
            "smtp_port": config.smtp_port,
            "username": config.username,
            "password": config.password,
            "from_email": config.from_email,
            "to_emails": config.to_emails,
            "enabled": config.enabled,
        }
        row.email_config = encryption.encrypt_json(config_dict)
        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info("Email notifications configured")
    return {"status": "configured", "channel": "email"}


@router.post("/notifications/telegram/configure")
async def configure_telegram(
    config: TelegramConfig,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """Configure Telegram bot"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        config_dict = {"bot_token": config.bot_token, "chat_id": config.chat_id, "enabled": config.enabled}
        row.telegram_config = encryption.encrypt_json(config_dict)
        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info("Telegram notifications configured")
    return {"status": "configured", "channel": "telegram"}


@router.post("/notifications/whatsapp/configure")
async def configure_whatsapp(
    config: WhatsAppConfig,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """
    Configure WhatsApp notifications via OpenWA.

    **Setup:**
    1. OpenWA will be embedded in backend (auto-starts)
    2. Scan QR code to link your WhatsApp
    3. Configure here with your phone number
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        config_dict = {
            "phone_number": config.phone_number,
            "openwa_url": config.openwa_url,
            "enabled": config.enabled,
            "chat_enabled": config.chat_enabled,
        }
        row.whatsapp_config = encryption.encrypt_json(config_dict)
        row.updated_at = datetime.utcnow()
        await session.commit()

    # Also configure WhatsApp service in runtime
    from app.services.whatsapp_service import whatsapp_service
    whatsapp_service.configure(
        phone_number=config.phone_number,
        enabled=config.enabled,
        openwa_url=config.openwa_url
    )

    logger.info("WhatsApp notifications configured")
    return {"status": "configured", "channel": "whatsapp"}


# ============ Trading Preferences ============

@router.get("/trading")
async def get_trading_preferences(device_id: str = Header(None, alias="X-Device-ID")):
    """Get trading preferences"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    if not row:
        return {
            "default_brokers": None,
            "routing_mode": "asset_class",
        }

    return {
        "default_brokers": row.default_brokers,
        "routing_mode": row.routing_mode or "asset_class",
    }


@router.post("/trading")
async def save_trading_preferences(
    preferences: TradingPreferences,
    device_id: str = Header(None, alias="X-Device-ID")
):
    """Save trading preferences"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Device settings not found")

        row.default_brokers = preferences.default_brokers
        row.routing_mode = preferences.routing_mode
        row.updated_at = datetime.utcnow()
        await session.commit()

    logger.info(f"Trading preferences saved: {preferences.routing_mode}")
    return {"success": True, "routing_mode": preferences.routing_mode}


# ============ System Settings ============

@router.get("/system")
async def get_system_settings():
    """Get system settings info"""
    return {
        "version": "1.0.0",
        "crypto_available": CRYPTO_AVAILABLE,
        "encryption_key_exists": Path("data/encryption.key").exists(),
    }


@router.post("/reset")
async def reset_all_settings(device_id: str = Header(None, alias="X-Device-ID")):
    """Reset all settings for current device"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            await session.delete(row)
            await session.commit()
            logger.info(f"Settings reset for device {device_id}")
            return {"status": "reset", "message": "All settings cleared"}

    return {"status": "not_found", "message": "No settings to reset"}


@router.post("/migrate-from-file")
async def migrate_from_file(
    device_id: str = Header(None, alias="X-Device-ID")
):
    """
    Migrate settings from settings_enhanced.json file to database.
    One-time migration helper.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    settings_file = Path("data/app_settings.json")
    if not settings_file.exists():
        return {"status": "skipped", "message": "No settings file found"}

    try:
        with open(settings_file, 'r') as f:
            file_settings = json.load(f)

        # Import settings into database
        async with async_session() as session:
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if not row:
                row = DeviceSettings(device_id=device_id)
                session.add(row)

            # Migrate brokers
            brokers = file_settings.get("brokers", {})
            if "alpaca" in brokers:
                b = brokers["alpaca"]
                row.alpaca_key = encryption.encrypt(b.get("api_key")) if b.get("api_key") else None
                row.alpaca_secret = encryption.encrypt(b.get("api_secret")) if b.get("api_secret") else None
                row.alpaca_paper = b.get("paper_trading", True)

            if "binance" in brokers:
                b = brokers["binance"]
                row.binance_key = encryption.encrypt(b.get("api_key")) if b.get("api_key") else None
                row.binance_secret = encryption.encrypt(b.get("api_secret")) if b.get("api_secret") else None

            # Migrate notifications
            notifications = file_settings.get("notifications", {})
            for channel, config in notifications.items():
                if config and config.get("enabled"):
                    config_key = f"{channel}_config"
                    if hasattr(row, config_key):
                        setattr(row, config_key, encryption.encrypt_json(config))

            row.updated_at = datetime.utcnow()
            await session.commit()

        # Delete file after successful migration
        settings_file.unlink()
        logger.info("Settings migrated from file to database")

        return {
            "status": "migrated",
            "message": "Settings migrated successfully. File deleted.",
        }

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============ Auto-Payout Endpoints ============

@router.post("/payout")
async def configure_payout(
    request: PayoutConfigRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Configure auto-payout settings.
    
    Payout Configuration:
    - payout_enabled: Enable/disable auto-payout
    - payout_percentage: % of daily profit to payout (0-100)
    - payout_schedule_hour: Hour (ET) to execute payout (0-23)
    - payout_destination: "crypto_wallet" | "forex_account" | "split"
    - crypto_wallet: USDT wallet address (ERC20/SOLANA/BSC)
    - crypto_chain: "ethereum" | "solana" | "bsc"
    - split_ratio: % to crypto if split (remainder to forex)
    - min_payout_threshold: Minimum profit before payout triggers
    
    All settings encrypted before storage.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        from app.services.encryption import EncryptionHelper
        encryption = EncryptionHelper()
        
        async with async_session() as session:
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                settings = DeviceSettings(device_id=device_id)
            
            # Encrypt and save payout config
            payout_json = json.dumps(request.payout_config)
            settings.payout_config = encryption.encrypt(payout_json)
            settings.updated_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Payout config saved for device {device_id}")
            
            return {
                "status": "saved",
                "config": request.payout_config,
            }
    
    except Exception as e:
        logger.error(f"Save payout config failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payout")
async def get_payout_config(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get auto-payout configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        from app.services.encryption import EncryptionHelper
        encryption = EncryptionHelper()
        
        async with async_session() as session:
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings or not settings.payout_config:
                return {
                    "configured": False,
                    "payout_config": {
                        "payout_enabled": False,
                        "payout_percentage": 50.0,
                        "payout_schedule_hour": 20,
                        "payout_destination": "crypto_wallet",
                        "crypto_wallet": "",
                        "crypto_chain": "ethereum",
                        "split_ratio": 50,
                        "min_payout_threshold": 10.0,
                    }
                }
            
            # Decrypt config
            config = encryption.decrypt_json(settings.payout_config)
            
            return {
                "configured": True,
                "payout_config": config or {},
            }
    
    except Exception as e:
        logger.error(f"Get payout config failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payout/test")
async def test_payout(
    request: PayoutTestRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Execute test auto-payout.
    
    Runs auto-payout logic with current configuration.
    Will skip if no profit available or already paid today.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        from app.services.payout_scheduler import get_payout_scheduler
        scheduler = get_payout_scheduler()
        
        # Execute immediate payout
        executed = await scheduler.execute_immediate_payout(request.portfolio_id)
        
        if executed:
            return {
                "executed": True,
                "status": "completed",
                "amount": executed.amount,
                "destination": executed.destination_type,
                "tx_hash": executed.transaction_hash[:20] if executed.transaction_hash else None,
            }
        else:
            return {
                "executed": False,
                "reason": "No profit available or already paid today",
            }
    
    except Exception as e:
        logger.error(f"Test payout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))