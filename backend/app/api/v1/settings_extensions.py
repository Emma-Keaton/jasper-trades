"""
Settings API Extensions - Market Data, Email, Discord Bot

Endpoints for configuring:
- Market data providers (CoinGecko, Alpha Vantage, Finnhub, etc.)
- Email service (SendGrid)
- Discord bot (two-way chat)
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any
import structlog

from app.database import get_db, async_session
from sqlalchemy import select
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings-extensions"])


# ============ Request Models ============

class MarketDataSettings(BaseModel):
    """Market data API keys"""
    alphavantage_key: Optional[str] = None
    finnhub_key: Optional[str] = None
    twelvedata_key: Optional[str] = None
    polygon_key: Optional[str] = None
    fred_key: Optional[str] = None
    coingecko_enabled: bool = True


class SendGridSettings(BaseModel):
    """SendGrid email configuration"""
    api_key: str
    from_email: str
    enabled: bool = True


class DiscordBotSettings(BaseModel):
    """Discord bot configuration"""
    bot_token: str
    guild_id: str
    channel_id: str
    enabled: bool = True
    chat_enabled: bool = True


# ============ Helper ============

def get_encryption() -> EncryptionHelper:
    return EncryptionHelper()


# ============ Market Data Endpoints ============

@router.post("/market-data")
async def save_market_data_settings(
    settings: MarketDataSettings,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save market data API keys."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.alphavantage_key = encryption.encrypt(settings.alphavantage_key) if settings.alphavantage_key else None
            row.finnhub_key = encryption.encrypt(settings.finnhub_key) if settings.finnhub_key else None
            row.twelvedata_key = encryption.encrypt(settings.twelvedata_key) if settings.twelvedata_key else None
            row.polygon_key = encryption.encrypt(settings.polygon_key) if settings.polygon_key else None
            row.fred_key = encryption.encrypt(settings.fred_key) if settings.fred_key else None
            row.coingecko_enabled = settings.coingecko_enabled
        else:
            row = DeviceSettings(
                device_id=device_id,
                alphavantage_key=encryption.encrypt(settings.alphavantage_key) if settings.alphavantage_key else None,
                finnhub_key=encryption.encrypt(settings.finnhub_key) if settings.finnhub_key else None,
                twelvedata_key=encryption.encrypt(settings.twelvedata_key) if settings.twelvedata_key else None,
                polygon_key=encryption.encrypt(settings.polygon_key) if settings.polygon_key else None,
                fred_key=encryption.encrypt(settings.fred_key) if settings.fred_key else None,
                coingecko_enabled=settings.coingecko_enabled,
            )
            session.add(row)

        await session.commit()

    logger.info(f"Market data settings saved for {device_id}")
    return {"success": True, "message": "Market data settings saved"}


@router.post("/market-data/test")
async def test_market_data_connection(
    request: Dict[str, str],
):
    """Test a market data API connection."""
    service = request.get("service")
    key = request.get("key")

    if not key:
        return {"valid": False, "message": "No API key provided"}

    # Test based on service
    if service == "alphavantage":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://www.alphavantage.co/query",
                    params={"function": "GLOBAL_QUOTE", "symbol": "AAPL", "apikey": key}
                )
                data = resp.json()
                if "Global Quote" in data and data["Global Quote"]:
                    return {"valid": True, "message": "Alpha Vantage connected"}
                elif "Note" in data:
                    return {"valid": False, "message": "API limit reached"}
                else:
                    return {"valid": False, "message": "Invalid API key"}
        except Exception as e:
            return {"valid": False, "message": f"Connection failed: {str(e)}"}

    elif service == "finnhub":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": "AAPL", "token": key}
                )
                data = resp.json()
                if data and "c" in data:  # 'c' = current price
                    return {"valid": True, "message": "Finnhub connected"}
                else:
                    return {"valid": False, "message": "Invalid API key"}
        except Exception as e:
            return {"valid": False, "message": f"Connection failed: {str(e)}"}

    return {"valid": True, "message": "Test not implemented for this service"}


# ============ Email (SendGrid) Endpoints ============

@router.post("/email/sendgrid")
async def save_sendgrid_settings(
    settings: SendGridSettings,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save SendGrid email configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()
    config = {
        "api_key": encryption.encrypt(settings.api_key) if settings.api_key else None,
        "from_email": settings.from_email,
        "enabled": settings.enabled,
    }

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.sendgrid_config = encryption.encrypt_json(config)
        else:
            row = DeviceSettings(
                device_id=device_id,
                sendgrid_config=encryption.encrypt_json(config),
            )
            session.add(row)

        await session.commit()

    logger.info(f"SendGrid settings saved for {device_id}")
    return {"success": True, "message": "SendGrid settings saved"}


# ============ Discord Bot Endpoints ============

@router.post("/discord-bot")
async def save_discord_bot_settings(
    settings: DiscordBotSettings,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save Discord bot configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()
    config = {
        "bot_token": encryption.encrypt(settings.bot_token),
        "guild_id": settings.guild_id,
        "channel_id": settings.channel_id,
        "enabled": settings.enabled,
        "chat_enabled": settings.chat_enabled,
    }

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.discord_bot_config = encryption.encrypt_json(config)
        else:
            row = DeviceSettings(
                device_id=device_id,
                discord_bot_config=encryption.encrypt_json(config),
            )
            session.add(row)

        await session.commit()

    logger.info(f"Discord bot settings saved for {device_id}")
    return {"success": True, "message": "Discord bot settings saved"}


@router.post("/discord/start")
async def start_discord_bot(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Start Discord bot with current configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    try:
        from app.services.discord_bot_service import get_discord_bot_service

        async with async_session() as session:
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if not row or not row.discord_bot_config:
                raise HTTPException(status_code=400, detail="Discord bot not configured")

            encryption = get_encryption()
            config = encryption.decrypt_json(row.discord_bot_config)

            if not config:
                raise HTTPException(status_code=400, detail="Invalid Discord config")

            bot = get_discord_bot_service()
            bot.configure({
                "bot_token": encryption.decrypt(config.get("bot_token")),
                "guild_id": config.get("guild_id"),
                "channel_id": config.get("channel_id"),
                "enabled": config.get("enabled"),
                "chat_enabled": config.get("chat_enabled"),
            })

            started = await bot.start()

            if not started:
                raise HTTPException(status_code=500, detail="Failed to start Discord bot")

        return {"success": True, "message": "Discord bot started"}

    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Discord bot library not installed: {str(e)}")
    except Exception as e:
        logger.error(f"Discord bot start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discord/test")
async def send_discord_test_message(
    request: Dict[str, str],
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Send test message to Discord."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    try:
        from app.services.discord_bot_service import get_discord_bot_service

        bot = get_discord_bot_service()
        
        if not bot.is_running:
            raise HTTPException(status_code=400, detail="Discord bot not running")

        message = request.get("message", "Test message from Jasper Trades")
        result = await bot.send_message(message)

        if result.get("success"):
            return {"success": True, "message": "Test message sent"}
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))

    except Exception as e:
        logger.error(f"Discord test message failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discord/status")
async def get_discord_bot_status(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get Discord bot status."""
    from app.services.discord_bot_service import get_discord_bot_service

    bot = get_discord_bot_service()
    return {"status": bot.get_status()}