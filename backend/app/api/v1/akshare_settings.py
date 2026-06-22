"""
AKShare Settings API
Configure Chinese stock trading settings per device.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from typing import Optional

from app.database import get_db
from app.models import DeviceSettings
from app.services.encryption import EncryptionService
from app.brokers.akshare_service import get_akshare_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings/akshare", tags=["AKShare Settings"])

encryption = EncryptionService()


@router.get("/")
async def get_akshare_settings(
    device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get AKShare settings for device"""
    if not device_id:
        raise HTTPException(status_code=400, detail="Device ID required")
    
    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create default settings
        settings = DeviceSettings(device_id=device_id)
        db.add(settings)
        await db.commit()
    
    # Decrypt AKShare config
    akshare_config = settings.akshare_config if settings else {}
    if isinstance(akshare_config, str):
        import json
        akshare_config = json.loads(akshare_config)
    
    return {
        "enabled": akshare_config.get("enabled", False),
        "paper_trading": akshare_config.get("paper_trading", True),
        "initial_capital": akshare_config.get("initial_capital", 1000000.0),
        "currency": akshare_config.get("currency", "CNY"),
        "connected": akshare_config.get("connected", False),
    }


@router.post("/")
async def save_akshare_settings(
    settings_data: dict,
    device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db)
):
    """Save AKShare settings for device"""
    if not device_id:
        raise HTTPException(status_code=400, detail="Device ID required")
    
    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = DeviceSettings(device_id=device_id)
        db.add(settings)
    
    # Update AKShare config
    import json
    settings.akshare_config = json.dumps(settings_data)
    await db.commit()
    
    # Update AKShare service if enabled
    if settings_data.get("enabled"):
        try:
            service = get_akshare_service()
            service.paper_trading = settings_data.get("paper_trading", True)
            service.initial_capital = float(settings_data.get("initial_capital", 1000000.0))
            service.currency = settings_data.get("currency", "CNY")
            await service.connect()
        except Exception as e:
            logger.error(f"Failed to update AKShare service: {e}")
    
    return {"success": True, "message": "AKShare settings saved"}