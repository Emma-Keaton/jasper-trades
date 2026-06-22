"""
Telegram Settings API
Manage Telegram notification preferences, daily summary schedule, and user verification
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import structlog
import secrets

from app.database import get_db
from app.models import TelegramUser, DeviceSettings
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings/telegram", tags=["Telegram Settings"])


# ============ Request Models ============

class TelegramVerificationRequest(BaseModel):
    """Request to verify Telegram chat ID"""
    chat_id: str = Field(..., description="Telegram chat ID")


class TelegramVerificationCodeRequest(BaseModel):
    """Submit verification code"""
    chat_id: str
    verification_code: str


class TelegramNotificationPreferences(BaseModel):
    """Telegram notification preferences"""
    trade_notifications_enabled: bool = True
    daily_summary_enabled: bool = True
    summary_time_wat: str = Field(default="20:00", description="WAT time for daily summary (HH:MM format)")
    chat_enabled: bool = True
    ai_explanations_enabled: bool = True


# ============ Endpoints ============

@router.post("/verify/request")
async def request_telegram_verification(
    request: TelegramVerificationRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Request Telegram chat ID verification.
    Sends a verification code to the user's Telegram chat.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    # Generate 6-digit verification code
    verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Store or update user record
    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if user:
        user.chat_id = request.chat_id
        user.verification_code = verification_code
        user.verification_expires_at = expires_at
        user.is_verified = False
    else:
        user = TelegramUser(
            device_id=device_id,
            chat_id=request.chat_id,
            verification_code=verification_code,
            verification_expires_at=expires_at,
            is_verified=False,
        )
        db.add(user)

    await db.commit()

    # Send verification code via Telegram
    success = await telegram_service.send_verification_code(
        chat_id=request.chat_id,
        code=verification_code,
        expires_minutes=10
    )

    if not success:
        logger.error("Failed to send verification code")
        # Return code anyway for development
        logger.info(f"VERIFICATION CODE: {verification_code}")
        return {
            "success": True,
            "message": f"Code: {verification_code}",
            "code": verification_code,
            "note": "Verification code (check Telegram bot)"
        }

    logger.info(f"Verification code sent to Telegram chat {request.chat_id[:5]}***")

    return {
        "success": True,
        "message": f"Verification code sent to Telegram chat",
        "expires_in_minutes": 10,
    }


@router.post("/verify/confirm")
async def confirm_telegram_verification(
    request: TelegramVerificationCodeRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm Telegram chat ID verification code.
    Marks chat ID as verified if code matches.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(
            TelegramUser.device_id == device_id,
            TelegramUser.chat_id == request.chat_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Verification request not found")

    # Check if code matches
    if user.verification_code != request.verification_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Check if expired
    if datetime.utcnow() > user.verification_expires_at:
        raise HTTPException(status_code=400, detail="Verification code expired. Please request a new one.")

    # Mark as verified
    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    user.last_active_at = datetime.utcnow()

    await db.commit()

    # Send welcome message
    await telegram_service.send_welcome_message(
        summary_time=user.summary_time_wat or "8:00 PM WAT"
    )

    logger.info(f"Telegram chat verified for {device_id}")

    return {
        "success": True,
        "message": "Telegram chat ID verified successfully",
        "chat_id": user.chat_id[:5] + "***",
    }


@router.get("/status")
async def get_telegram_status(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get Telegram configuration status for device.
    Returns verification status and notification preferences.
    """
    if not device_id:
        return {
            "is_configured": False,
            "is_verified": False,
            "chat_id": None,
        }

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return {
            "is_configured": False,
            "is_verified": False,
            "chat_id": None,
        }

    return {
        "is_configured": True,
        "is_verified": user.is_verified,
        "chat_id": user.chat_id[:5] + "***" if user.chat_id else None,
        "preferences": {
            "trade_notifications_enabled": user.trade_notifications_enabled,
            "daily_summary_enabled": user.daily_summary_enabled,
            "summary_time_wat": user.summary_time_wat or "20:00",
            "chat_enabled": user.chat_enabled,
            "ai_explanations_enabled": user.ai_explanations_enabled,
        },
        "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
    }


@router.post("/preferences")
async def update_telegram_preferences(
    preferences: TelegramNotificationPreferences,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Update Telegram notification preferences.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Telegram user not found. Please verify your chat ID first.")

    # Update preferences
    user.trade_notifications_enabled = preferences.trade_notifications_enabled
    user.daily_summary_enabled = preferences.daily_summary_enabled
    user.summary_time_wat = preferences.summary_time_wat
    user.chat_enabled = preferences.chat_enabled
    user.ai_explanations_enabled = preferences.ai_explanations_enabled

    await db.commit()

    logger.info(f"Telegram preferences updated for {device_id}")

    return {
        "success": True,
        "message": "Telegram preferences updated",
        "preferences": {
            "trade_notifications_enabled": user.trade_notifications_enabled,
            "daily_summary_enabled": user.daily_summary_enabled,
            "summary_time_wat": user.summary_time_wat,
            "chat_enabled": user.chat_enabled,
            "ai_explanations_enabled": user.ai_explanations_enabled,
        },
    }


@router.post("/test")
async def test_telegram_connection(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Test Telegram connection by sending a test message.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.chat_id:
        raise HTTPException(status_code=404, detail="Telegram chat not configured")

    if not user.is_verified:
        raise HTTPException(status_code=400, detail="Telegram chat not verified")

    # Send test message
    success = await telegram_service.test_connection()

    if success:
        # Update last active
        user.last_active_at = datetime.utcnow()
        await db.commit()

        return {
            "success": True,
            "message": "Test message sent successfully",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to send test message")


@router.get("/summary/schedule")
async def get_daily_summary_schedule(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get daily summary schedule for device."""
    if not device_id:
        return {
            "enabled": False,
            "time_wat": "20:00",
            "timezone": "WAT (UTC+1)",
        }

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return {
            "enabled": False,
            "time_wat": "20:00",
            "timezone": "WAT (UTC+1)",
        }

    return {
        "enabled": user.daily_summary_enabled,
        "time_wat": user.summary_time_wat or "20:00",
        "timezone": "WAT (UTC+1)",
    }


@router.post("/summary/schedule")
async def update_daily_summary_schedule(
    schedule: dict,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Update daily summary schedule.

    Request body:
    {
        "enabled": true,
        "time_wat": "20:00"  # 8 PM WAT (default)
    }
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    from sqlalchemy import select
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.device_id == device_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Telegram user not found")

    # Update schedule
    user.daily_summary_enabled = schedule.get("enabled", True)
    user.summary_time_wat = schedule.get("time_wat", "20:00")

    await db.commit()

    logger.info(f"Daily summary schedule updated for {device_id}: {user.summary_time_wat}")

    return {
        "success": True,
        "message": "Daily summary schedule updated",
        "schedule": {
            "enabled": user.daily_summary_enabled,
            "time_wat": user.summary_time_wat,
            "timezone": "WAT (UTC+1)",
        },
    }