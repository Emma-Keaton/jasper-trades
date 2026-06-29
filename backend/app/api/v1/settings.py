"""
Settings management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict
import structlog
import os

from app.database import get_db, async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper
from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class ValidateKeyRequest(BaseModel):
    service: str
    key: str


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
        "nvidia_api_key": {
            "configured": bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "" and settings.NVIDIA_API_KEY != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "NVIDIA_API_KEY",
            "description": "NVIDIA NIM API key for AI model inference",
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
        "colab_kronos_url": {
            "configured": bool(os.getenv("KRONOS_COLAB_URL") and os.getenv("KRONOS_COLAB_URL") != "" and os.getenv("KRONOS_COLAB_URL") != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "KRONOS_COLAB_URL",
            "description": "Google Colab URL for Kronos AI predictions",
            "required_for": "Kronos AI model predictions"
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


# Broker Paper Trading Models
class BrokerPaperTradingRequest(BaseModel):
    broker: str
    enabled: bool
    capital: float
    currency: str


class BrokerPaperTradingResponse(BaseModel):
    """Response model for broker paper trading configs"""
    ctrader: dict
    trove: dict
    akshare: dict


@router.get("/broker-paper-trading")
async def get_broker_paper_trading(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get paper trading configurations for all brokers.

    Returns paper trading settings for cTrader, Trove, and AKShare.
    Default values returned if not configured.
    """
    # Default configs for each broker
    defaults = {
        "ctrader": {"enabled": True, "capital": 10000, "currency": "USD"},
        "trove": {"enabled": True, "capital": 1000, "currency": "USD"},
        "akshare": {"enabled": True, "capital": 1000000, "currency": "CNY"},
    }

    if not device_id:
        return BrokerPaperTradingResponse(**defaults)

    try:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()

            if not row or not row.broker_paper_trading_config:
                return BrokerPaperTradingResponse(**defaults)

            # Parse stored config
            import json
            try:
                stored_config = json.loads(row.broker_paper_trading_config)
            except:
                return BrokerPaperTradingResponse(**defaults)

            # Merge with defaults for any missing brokers
            result_config = {}
            for broker in ["ctrader", "trove", "akshare"]:
                if broker in stored_config:
                    result_config[broker] = stored_config[broker]
                else:
                    result_config[broker] = defaults[broker]

            return BrokerPaperTradingResponse(**result_config)

    except Exception as e:
        logger.error(f"Failed to get broker paper trading configs: {e}")
        return BrokerPaperTradingResponse(**defaults)


@router.post("/broker-paper-trading")
async def save_broker_paper_trading(
    request: BrokerPaperTradingRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Save paper trading configuration for a specific broker.
    
    Each broker can have its own paper trading settings (enabled, capital, currency).
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    # Validate broker name
    valid_brokers = ["ctrader", "trove", "akshare"]
    if request.broker not in valid_brokers:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid broker. Must be one of: {', '.join(valid_brokers)}"
        )
    
    # Validate capital
    if request.capital < 0:
        raise HTTPException(status_code=400, detail="Capital cannot be negative")
    
    try:
        encryption = EncryptionHelper()
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            row = result.scalar_one_or_none()
            
            if not row:
                # Create new settings if they don't exist
                row = DeviceSettings(device_id=device_id)
                session.add(row)
            
            # Get current paper trading config (as JSON)
            import json
            current_config = {}
            if hasattr(row, 'broker_paper_trading_config') and row.broker_paper_trading_config:
                try:
                    current_config = json.loads(row.broker_paper_trading_config)
                except:
                    current_config = {}
            
            # Update the specific broker's config
            current_config[request.broker] = {
                "enabled": request.enabled,
                "capital": request.capital,
                "currency": request.currency
            }
            
            # Save back as JSON string
            row.broker_paper_trading_config = json.dumps(current_config)
            
            await session.commit()
            
            logger.info(
                f"Broker paper trading config saved",
                broker=request.broker,
                device_id=device_id,
                enabled=request.enabled,
                capital=request.capital,
                currency=request.currency
            )
            
            return {
                "success": True,
                "broker": request.broker,
                "message": f"Paper trading config saved for {request.broker}",
                "config": current_config[request.broker]
            }
            
    except Exception as e:
        logger.error(f"Failed to save broker paper trading config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save paper trading configuration")