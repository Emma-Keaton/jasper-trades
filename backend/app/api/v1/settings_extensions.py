"""
Settings API Extensions - Market Data, Email, Discord Bot

Endpoints for configuring:
- Market data providers (CoinGecko, Alpha Vantage, Finnhub, etc.)
- Email service (SendGrid)
- Discord bot (two-way chat)
- Environment mode (sandbox/live)
- Trove API (Nigerian/US stocks)
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
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


class EnvironmentModeRequest(BaseModel):
    """Environment mode toggle request"""
    environment_mode: Literal["sandbox", "live"] = Field(..., description="Trading mode: 'sandbox' or 'live'")


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


# ============ Environment Mode Endpoints ============

@router.post("/environment")
async def save_environment_mode(
    request: EnvironmentModeRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save environment mode (sandbox/live) for device.
    
    This setting controls whether cTrader connections execute real trades or demo trades.
    The mode is stored per-device via X-Device-ID header.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    if request.environment_mode not in ["sandbox", "live"]:
        raise HTTPException(status_code=400, detail="environment_mode must be 'sandbox' or 'live'")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.environment_mode = request.environment_mode
        else:
            row = DeviceSettings(
                device_id=device_id,
                environment_mode=request.environment_mode,
            )
            session.add(row)

        await session.commit()

    logger.info(f"Environment mode set to {request.environment_mode} for {device_id}")
    return {"success": True, "environment_mode": request.environment_mode}


@router.get("/environment")
async def get_environment_mode(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get current environment mode (sandbox/live).

    Returns the trading mode setting for the current device.
    """
    if not device_id:
        # Return default mode if no device ID provided
        return {"environment_mode": "sandbox"}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings.environment_mode).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    return {"environment_mode": row if row else "sandbox"}


# ============ Trading Mode Endpoints (paper / live) ============

class TradingModeRequest(BaseModel):
    trading_mode: Literal["practice", "live"]


@router.post("/trading-mode")
async def save_trading_mode(
    request: TradingModeRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save the frontend trading mode (paper or live) for a device."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.trading_mode = request.trading_mode
        else:
            row = DeviceSettings(
                device_id=device_id,
                trading_mode=request.trading_mode,
            )
            session.add(row)

        await session.commit()

    logger.info(f"Trading mode set to {request.trading_mode} for {device_id}")
    return {"success": True, "trading_mode": request.trading_mode}


@router.get("/trading-mode")
async def get_trading_mode(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get the current trading mode (paper/live) for a device."""
    if not device_id:
        return {"trading_mode": "practice"}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings.trading_mode).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    return {"trading_mode": row if row else "practice"}


# ============ UI Preferences Endpoints ============

class PreferencesRequest(BaseModel):
    preferences: Dict[str, Any]


@router.get("/preferences")
async def get_preferences(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get frontend UI preferences (ai_running, agent_configs, sections, onboarding) for a device."""
    import json
    if not device_id:
        return {"preferences": {}}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings.preferences).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

    if not row:
        return {"preferences": {}}
    try:
        return {"preferences": json.loads(row)}
    except (TypeError, ValueError):
        return {"preferences": {}}


@router.post("/preferences")
async def save_preferences(
    request: PreferencesRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save frontend UI preferences for a device (shallow merge on top-level keys)."""
    import json
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        current: Dict[str, Any] = {}
        if row and row.preferences:
            try:
                current = json.loads(row.preferences)
            except (TypeError, ValueError):
                current = {}

        # Shallow merge top-level keys so callers can update one slice at a time.
        for key, value in request.preferences.items():
            if key in current and isinstance(current[key], dict) and isinstance(value, dict):
                current[key] = {**current[key], **value}
            else:
                current[key] = value

        if row:
            row.preferences = json.dumps(current)
        else:
            row = DeviceSettings(device_id=device_id, preferences=json.dumps(current))
            session.add(row)

        await session.commit()

    logger.info(f"Saved UI preferences for {device_id}")
    return {"success": True, "preferences": current}


# ============ Trove API Endpoints ============

class TroveSettingsRequest(BaseModel):
    """Trove API configuration"""
    trove_api_key: str
    trove_base_url: Optional[str] = "https://sandbox.api.trovefinance.com/v1"
    trove_enabled: bool = True
    trove_sandbox: bool = True


class CurrencyPreferenceRequest(BaseModel):
    """Currency preference settings"""
    default_currency: Literal["USD", "NGN"] = "USD"
    currency_conversion_enabled: bool = True


class NairaBankDetailsRequest(BaseModel):
    """Nigerian bank account details for payouts"""
    naira_bank_enabled: bool = True
    bank_account_number: str = Field(..., min_length=10, max_length=10)
    bank_code: str
    account_name: str
    bank_name: str


class PaymentGatewayRequest(BaseModel):
    """Payment gateway API keys for Nigerian bank payouts"""
    naira_bank_enabled: bool = True
    paystack_api_key: Optional[str] = None
    flutterwave_api_key: Optional[str] = None
    paystack_enabled: bool = False
    flutterwave_enabled: bool = False


@router.post("/trove")
async def save_trove_settings(
    settings: TroveSettingsRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save Trove API configuration.

    Trove enables trading of:
    - US stocks (AAPL, TSLA, etc.)
    - Nigerian NGX stocks (DANGCEM, MTNN, etc.)
    - Fractional share trading
    - Multi-currency support (USD/NGN)
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.trove_api_key = encryption.encrypt(settings.trove_api_key)
            row.trove_base_url = settings.trove_base_url
            row.trove_enabled = settings.trove_enabled
            row.trove_sandbox = settings.trove_sandbox
        else:
            row = DeviceSettings(
                device_id=device_id,
                trove_api_key=encryption.encrypt(settings.trove_api_key),
                trove_base_url=settings.trove_base_url,
                trove_enabled=settings.trove_enabled,
                trove_sandbox=settings.trove_sandbox,
            )
            session.add(row)

        await session.commit()

    logger.info(f"Trove settings saved for {device_id}")
    return {
        "success": True,
        "message": "Trove API settings saved",
        "trove_enabled": settings.trove_enabled,
        "sandbox": settings.trove_sandbox,
    }


@router.get("/trove")
async def get_trove_settings(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get Trove API configuration (API key masked for security)."""
    if not device_id:
        return {
            "trove_enabled": False,
            "trove_base_url": None,
            "trove_sandbox": True,
            "is_connected": False,
        }

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row:
            return {
                "trove_enabled": False,
                "trove_base_url": None,
                "trove_sandbox": True,
                "is_connected": False,
            }

        return {
            "trove_enabled": row.trove_enabled or False,
            "trove_base_url": row.trove_base_url,
            "trove_sandbox": row.trove_sandbox if row.trove_sandbox is not None else True,
            "trove_account_id": row.trove_account_id,
            "is_connected": bool(row.trove_api_key and row.trove_enabled),
        }


@router.post("/trove/test")
async def test_trove_connection(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Test Trove API connection."""
    if not device_id:
        return {"valid": False, "message": "X-Device-ID header required"}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row or not row.trove_api_key:
            return {"valid": False, "message": "Trove API key not configured"}

        # Decrypt API key
        encryption = get_encryption()
        api_key = encryption.decrypt(row.trove_api_key)
        base_url = row.trove_base_url or "https://sandbox.api.trovefinance.com/v1"

        # Test connection
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{base_url}/account",
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    account_id = data.get("account_id")
                    # Store account ID for future use
                    row.trove_account_id = account_id
                    await session.commit()

                    return {
                        "valid": True,
                        "message": "Trove API connected",
                        "account_id": account_id,
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"API error: {response.status_code}",
                    }

        except Exception as e:
            return {"valid": False, "message": f"Connection failed: {str(e)}"}


@router.post("/currency/preference")
async def save_currency_preference(
    request: CurrencyPreferenceRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save currency preference (USD or NGN).

    This setting controls how monetary values are displayed throughout the app.
    All values can be toggled between USD and NGN with real-time conversion.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.default_currency = request.default_currency
            row.currency_conversion_enabled = request.currency_conversion_enabled
        else:
            row = DeviceSettings(
                device_id=device_id,
                default_currency=request.default_currency,
                currency_conversion_enabled=request.currency_conversion_enabled,
            )
            session.add(row)

        await session.commit()

    logger.info(f"Currency preference set to {request.default_currency} for {device_id}")
    return {
        "success": True,
        "default_currency": request.default_currency,
        "conversion_enabled": request.currency_conversion_enabled,
    }


@router.get("/currency/preference")
async def get_currency_preference(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get current currency preference."""
    if not device_id:
        return {"default_currency": "USD", "currency_conversion_enabled": True}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings.default_currency, DeviceSettings.currency_conversion_enabled)
            .where(DeviceSettings.device_id == device_id)
        )
        row = result.first()

        if not row:
            return {"default_currency": "USD", "currency_conversion_enabled": True}

        return {
            "default_currency": row.default_currency or "USD",
            "currency_conversion_enabled": row.currency_conversion_enabled if row.currency_conversion_enabled is not None else True,
        }


@router.post("/payout/naira-bank")
async def save_naira_bank_details(
    request: NairaBankDetailsRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save Nigerian bank account details for NGN payouts.

    This enables auto-payout to Nigerian bank accounts in addition to crypto wallets.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()
    config = {
        "naira_bank_enabled": request.naira_bank_enabled,
        "bank_account_number": request.bank_account_number,
        "bank_code": request.bank_code,
        "account_name": request.account_name,
        "bank_name": request.bank_name,
    }

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.naira_bank_details = encryption.encrypt_json(config)
        else:
            row = DeviceSettings(
                device_id=device_id,
                naira_bank_details=encryption.encrypt_json(config),
            )
            session.add(row)

        await session.commit()

    logger.info(f"Naira bank details saved for {device_id}")
    return {"success": True, "message": "Nigerian bank details saved"}


@router.get("/payout/naira-bank")
async def get_naira_bank_details(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get Nigerian bank account details (account number masked)."""
    if not device_id:
        return {"naira_bank_enabled": False}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if not row or not row.naira_bank_details:
            return {"naira_bank_enabled": False}

        encryption = get_encryption()
        config = encryption.decrypt_json(row.naira_bank_details)

        if not config:
            return {"naira_bank_enabled": False}

        # Mask account number for security
        account_number = config.get("bank_account_number", "")
        masked_number = f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"

        return {
            "naira_bank_enabled": config.get("naira_bank_enabled", False),
            "bank_account_number": masked_number,
            "account_name": config.get("account_name"),
            "bank_name": config.get("bank_name"),
            "bank_code": config.get("bank_code"),
        }


@router.post("/payment-gateways")
async def save_payment_gateways(
    request: PaymentGatewayRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save payment gateway API keys (Paystack/Flutterwave) for Nigerian bank payouts.

    These keys are used for:
    - Dynamic bank list fetching
    - CBN NIP account validation
    - Bank transfer processing

    Keys are encrypted before storing in database.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = get_encryption()
    config = {
        "naira_bank_enabled": request.naira_bank_enabled,
        "paystack_api_key": encryption.encrypt(request.paystack_api_key) if request.paystack_api_key else None,
        "flutterwave_api_key": encryption.encrypt(request.flutterwave_api_key) if request.flutterwave_api_key else None,
        "paystack_enabled": request.paystack_enabled,
        "flutterwave_enabled": request.flutterwave_enabled,
    }

    async with async_session() as session:
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = result.scalar_one_or_none()

        if row:
            row.naira_bank_details = encryption.encrypt_json(config)
        else:
            row = DeviceSettings(
                device_id=device_id,
                naira_bank_details=encryption.encrypt_json(config),
            )
            session.add(row)

        await session.commit()

    logger.info(f"Payment gateway settings saved for {device_id}")
    return {
        "success": True,
        "message": "Payment gateway settings saved",
        "paystack_enabled": request.paystack_enabled,
        "flutterwave_enabled": request.flutterwave_enabled,
    }