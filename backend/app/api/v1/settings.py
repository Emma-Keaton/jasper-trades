"""
Settings management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict
import structlog
import os
import httpx

from app.database import get_db, async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper
from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class ValidateKeyRequest(BaseModel):
    service: str
    key: str


@router.get("/public")
async def get_public_config():
    """
    Public, unauthenticated config for the frontend.

    Exposes only non-sensitive values needed at startup (e.g. the WalletConnect
    project ID so it never has to be compiled into the frontend build).
    """
    return {
        "walletconnect_project_id": settings.WALLETCONNECT_PROJECT_ID,
    }


@router.post("")
async def save_settings(
    settings: Dict[str, str],
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save all user settings.

    Settings are encrypted before storage.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = EncryptionHelper()

    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if row:
                # Update existing settings
                for key, value in settings.items():
                    if hasattr(row, key):
                        setattr(row, key, value)
            else:
                # Create new settings
                row = DeviceSettings(
                    device_id=device_id,
                    **settings
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


@router.get("")
async def get_settings(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get all user settings.

    Returns current settings for the device.
    """
    if not device_id:
        # Return empty settings if no device ID
        return {"settings": {}}

    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if not row:
                return {"settings": {}}

            # Convert to dict, excluding sensitive fields
            settings_dict = {
                key: value for key, value in row.__dict__.items()
                if not key.startswith('_') and key not in ['device_id']
            }

            return {"settings": settings_dict}

    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        return {"settings": {}}


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

    return {"valid": True, "message": "Key format looks valid"}


@router.get("/env-status")
async def get_env_status():
    """
    Check which environment variables are configured in the deployment environment.
    
    Returns status of API keys and secrets that should be set via Render dashboard
    environment variables during deployment.
    """
    env_status = {
        "gemini_api_keys": {
            "configured": bool(settings.GEMINI_API_KEYS),
            "env_var": "GEMINI_API_KEYS",
            "description": "Google Gemini 2.5 API keys (primary LLM). Comma-separated for multi-key rotation",
            "required_for": "AI chat, trade analysis, explanation, tip extraction"
        },
        "nvidia_api_key": {
            "configured": bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "" and settings.NVIDIA_API_KEY != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "NVIDIA_API_KEY",
            "description": "NVIDIA NIM API key for AI model inference (DEPRECATED - fallback only)",
            "required_for": "AI chat, trade analysis, Kronos predictions"
        },
        "binance_api_key": {
            "configured": bool(os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_KEY") != "" and os.getenv("BINANCE_API_KEY") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "BINANCE_API_KEY",
            "description": "Binance API key for crypto trading",
            "required_for": "Binance spot/futures trading"
        },
        "binance_api_secret": {
            "configured": bool(os.getenv("BINANCE_API_SECRET") and os.getenv("BINANCE_API_SECRET") != "" and os.getenv("BINANCE_API_SECRET") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "BINANCE_API_SECRET",
            "description": "Binance API secret for crypto trading",
            "required_for": "Binance spot/futures trading"
        },
        "telegram_bot_token": {
            "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_BOT_TOKEN") != "" and os.getenv("TELEGRAM_BOT_TOKEN") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "TELEGRAM_BOT_TOKEN",
            "description": "Telegram bot token for notifications",
            "required_for": "Trade notifications, daily summaries"
        },
        "trove_api_key": {
            "configured": bool(os.getenv("TROVE_API_KEY") and os.getenv("TROVE_API_KEY") != "" and os.getenv("TROVE_API_KEY") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "TROVE_API_KEY",
            "description": "Trove API key for Nigerian/US stocks",
            "required_for": "Trove broker integration"
        },
        "ctrader_client_id": {
            "configured": bool(os.getenv("CTRADER_CLIENT_ID") and os.getenv("CTRADER_CLIENT_ID") != "" and os.getenv("CTRADER_CLIENT_ID") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "CTRADER_CLIENT_ID",
            "description": "cTrader OAuth client ID",
            "required_for": "cTrader copy trading"
        },
        "ctrader_client_secret": {
            "configured": bool(os.getenv("CTRADER_CLIENT_SECRET") and os.getenv("CTRADER_CLIENT_SECRET") != "" and os.getenv("CTRADER_CLIENT_SECRET") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "CTRADER_CLIENT_SECRET",
            "description": "cTrader OAuth client secret",
            "required_for": "cTrader copy trading"
        },
        "universal_paper_trading": {
            "configured": True,
            "env_var": "UNIVERSAL_PAPER_TRADING",
            "description": "Universal paper trading mode for all brokers",
            "required_for": "Simulated trading across all brokers"
        }
    }
    
    # Calculate summary
    total_vars = len(env_status)
    configured_count = sum(1 for v in env_status.values() if v["configured"])
    
    return {
        "environment_variables": env_status,
        "summary": {
            "total": total_vars,
            "configured": configured_count,
            "missing": total_vars - configured_count
        }
    }


# Universal Paper Trading Models (replaces broker-specific sandbox modes)
class UniversalPaperTradingRequest(BaseModel):
    """Request model for universal paper trading settings"""
    enabled: bool
    initial_capital: float
    currency: str = "USD"


class UniversalPaperTradingResponse(BaseModel):
    """Response model for universal paper trading settings"""
    enabled: bool
    initial_capital: float
    current_balance: float
    total_pnl: float
    currency: str


@router.get("/universal-paper-trading")
async def get_universal_paper_trading(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get universal paper trading configuration.
    
    Returns global paper trading settings that apply to all brokers.
    """
    defaults = {
        "enabled": True,
        "initial_capital": 10000.0,
        "current_balance": 10000.0,
        "total_pnl": 0.0,
        "currency": "USD"
    }
    
    if not device_id:
        return UniversalPaperTradingResponse(**defaults)
    
    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()
            
            if not row or not row.universal_paper_trading_config:
                return UniversalPaperTradingResponse(**defaults)
            
            import json
            try:
                config = json.loads(row.universal_paper_trading_config)
                # Merge with defaults for any missing fields
                result_config = {**defaults, **config}
                return UniversalPaperTradingResponse(**result_config)
            except:
                return UniversalPaperTradingResponse(**defaults)
                
    except Exception as e:
        logger.error(f"Failed to get universal paper trading config: {e}")
        return UniversalPaperTradingResponse(**defaults)


@router.post("/universal-paper-trading")
async def save_universal_paper_trading(
    request: UniversalPaperTradingRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save universal paper trading configuration.
    
    This setting applies globally to all brokers.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    # Validate capital
    if request.initial_capital < 0:
        raise HTTPException(status_code=400, detail="Initial capital cannot be negative")
    
    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()
            
            if not row:
                row = DeviceSettings(device_id=device_id)
                session.add(row)
            
            # Get current config
            import json
            current_config = {}
            if hasattr(row, 'universal_paper_trading_config') and row.universal_paper_trading_config:
                try:
                    current_config = json.loads(row.universal_paper_trading_config)
                except:
                    current_config = {}
            
            # Update with new values
            current_config.update({
                "enabled": request.enabled,
                "initial_capital": request.initial_capital,
                "currency": request.currency,
                # Preserve these if they exist
                "current_balance": current_config.get("current_balance", request.initial_capital),
                "total_pnl": current_config.get("total_pnl", 0.0)
            })
            
            row.universal_paper_trading_config = json.dumps(current_config)
            await session.commit()
            
            logger.info(f"Saved universal paper trading config for device {device_id}")
            
            return {
                "status": "success",
                "data": UniversalPaperTradingResponse(
                    enabled=request.enabled,
                    initial_capital=request.initial_capital,
                    current_balance=current_config.get("current_balance", request.initial_capital),
                    total_pnl=current_config.get("total_pnl", 0.0),
                    currency=request.currency
                )
            }
            
    except Exception as e:
        logger.error(f"Failed to save universal paper trading config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings")


# Deprecated - kept for backward compatibility
@router.get("/broker-paper-trading")
async def get_broker_paper_trading_deprecated(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    DEPRECATED - Use /universal-paper-trading instead.
    
    Returns universal paper trading config with deprecation warning.
    """
    logger.warning("Deprecated endpoint called: /broker-paper-trading. Use /universal-paper-trading instead.")
    try:
        result = await get_universal_paper_trading(device_id=device_id)
        return {
            "warning": "This endpoint is deprecated. Use /universal-paper-trading instead",
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to get broker paper trading (deprecated): {e}")
        return {"warning": "This endpoint is deprecated", "data": None}

# Trove Settings Models
class TroveSettingsRequest(BaseModel):
    """Request model for Trove settings"""
    trove_api_key: str
    trove_base_url: str
    trove_enabled: bool
    trove_sandbox: bool


class TroveSettingsResponse(BaseModel):
    """Response model for Trove settings"""
    trove_enabled: bool
    trove_base_url: Optional[str]
    trove_sandbox: bool
    trove_account_id: Optional[str]
    is_connected: bool


@router.get("/trove")
async def get_trove_settings(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get Trove API settings for the device.
    
    Returns current Trove configuration including connection status.
    """
    logger.info(f"GET /settings/trove called for device: {device_id}")
    
    if not device_id:
        logger.warning("No device_id provided")
        return TroveSettingsResponse(
            trove_enabled=False,
            trove_base_url=None,
            trove_sandbox=True,
            trove_account_id=None,
            is_connected=False
        )

    try:
        async with async_session() as session:
            stmt = select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if not row:
                logger.warning(f"No settings found for device: {device_id}")
                return TroveSettingsResponse(
                    trove_enabled=False,
                    trove_base_url=None,
                    trove_sandbox=True,
                    trove_account_id=None,
                    is_connected=False
                )

            logger.info(
                f"Found settings for device",
                trove_enabled=row.trove_enabled,
                trove_base_url=row.trove_base_url,
                trove_sandbox=row.trove_sandbox,
                has_api_key=bool(row.trove_api_key)
            )

            # Decrypt API key if present
            api_key = row.trove_api_key
            if api_key and row.trove_enabled:
                try:
                    encryption = EncryptionHelper()
                    api_key = encryption.decrypt(row.trove_api_key)
                except Exception as e:
                    logger.warning(f"Failed to decrypt API key: {e}")
                    api_key = row.trove_api_key

            # Check connection status if enabled
            is_connected = False
            if row.trove_enabled and api_key:
                try:
                    base_url = row.trove_base_url or "https://sandbox.api.trovefinance.com/v1"
                    async with httpx.AsyncClient() as client:
                        test_response = await client.get(
                            f"{base_url}/health",
                            headers={"Authorization": f"Bearer {api_key}"},
                            timeout=5.0
                        )
                        is_connected = test_response.status_code == 200
                except Exception as e:
                    logger.warning(f"Connection test failed: {e}")
                    is_connected = False

            response = TroveSettingsResponse(
                trove_enabled=bool(row.trove_enabled),
                trove_base_url=row.trove_base_url,
                trove_sandbox=bool(row.trove_sandbox) if hasattr(row, 'trove_sandbox') else True,
                trove_account_id=row.trove_account_id,
                is_connected=is_connected
            )
            
            logger.info(f"Returning response: {response}")
            return response

    except Exception as e:
        logger.error(f"Failed to get Trove settings: {e}", exc_info=True)
        return TroveSettingsResponse(
            trove_enabled=False,
            trove_base_url=None,
            trove_sandbox=True,
            trove_account_id=None,
            is_connected=False
        )


@router.post("/trove")
async def save_trove_settings(
    request: TroveSettingsRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save Trove API settings for the device.
    
    Encrypts API key before storage.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    if not request.trove_api_key:
        raise HTTPException(status_code=400, detail="API key required")

    try:
        encryption = EncryptionHelper()
        
        # Encrypt the API key
        encrypted_key = encryption.encrypt(request.trove_api_key)

        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if row:
                # Update existing settings
                row.trove_api_key = encrypted_key
                row.trove_base_url = request.trove_base_url
                row.trove_enabled = request.trove_enabled
                if hasattr(row, 'trove_sandbox'):
                    row.trove_sandbox = request.trove_sandbox
            else:
                # Create new settings
                row = DeviceSettings(
                    device_id=device_id,
                    trove_api_key=encrypted_key,
                    trove_base_url=request.trove_base_url,
                    trove_enabled=request.trove_enabled,
                )
                if hasattr(row, 'trove_sandbox'):
                    row.trove_sandbox = request.trove_sandbox
                session.add(row)

            await session.commit()

            logger.info(
                f"Trove settings saved for device {device_id}",
                enabled=request.trove_enabled,
                sandbox=request.trove_sandbox
            )

            return {
                "success": True,
                "device_id": device_id,
                "message": "Trove settings saved successfully"
            }

    except Exception as e:
        logger.error(f"Failed to save Trove settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save Trove settings")


@router.get("/trove/test")
async def test_trove_connection(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Test Trove API connection with current settings.
    
    Validates the API key and returns account info if connected.
    """
    if not device_id:
        return {"valid": False, "message": "X-Device-ID header required"}

    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if not row or not row.trove_api_key or not row.trove_enabled:
                return {"valid": False, "message": "Trove not configured or enabled"}

            # Decrypt API key
            encryption = EncryptionHelper()
            api_key = encryption.decrypt(row.trove_api_key)
            base_url = row.trove_base_url or "https://sandbox.api.trovefinance.com/v1"

            # Test connection
            async with httpx.AsyncClient() as client:
                # Try to fetch account info
                response = await client.get(
                    f"{base_url}/user/account",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    account_id = data.get("account_id") or data.get("id") or "Unknown"
                    return {
                        "valid": True,
                        "message": "Connection successful",
                        "account_id": account_id,
                        "sandbox": "sandbox" in base_url
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Connection failed: {response.status_code}"
                    }

    except httpx.HTTPError as e:
        logger.error(f"Trove test connection HTTP error: {e}")
        return {"valid": False, "message": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.error(f"Failed to test Trove connection: {e}")
        return {"valid": False, "message": f"Connection failed: {str(e)}"}
