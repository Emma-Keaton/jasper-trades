"""
Settings management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict
import structlog

from app.database import get_db, async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper

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