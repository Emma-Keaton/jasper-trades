"""
Telegram Webhook Endpoint
Receives updates from Telegram instead of polling
For production deployment (Render, Vercel, etc.)
"""
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from telegram import Update
import structlog
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import TelegramUser

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Telegram webhook endpoint.
    Telegram sends updates here when configured for webhooks.
    
    All messages are processed and responses sent via the bot service.
    """
    try:
        # Get raw JSON from request
        data = await request.json()
        logger.info(f"Telegram webhook received update: {data.get('update_id')}")

        # Convert to Update object
        update = Update.de_json(data)
        
        # Process the update
        from app.services.telegram_bot_service import telegram_bot_service
        
        if not telegram_bot_service or not telegram_bot_service.application:
            logger.error("Telegram bot service not initialized")
            raise HTTPException(status_code=503, detail="Bot service not ready")

        # Process update through the application
        await telegram_bot_service.application.process_update(update)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/webhook/info")
async def get_webhook_info():
    """Get current webhook configuration"""
    from app.services.telegram_bot_service import telegram_bot_service
    
    if not telegram_bot_service or not telegram_bot_service.bot:
        return {
            "configured": False,
            "webhook_url": "Not configured",
            "has_webhook": False,
        }

    try:
        webhook_info = await telegram_bot_service.bot.get_webhook_info()
        return {
            "configured": True,
            "webhook_url": webhook_info.url or "Not set",
            "has_webhook": bool(webhook_info.url),
            "pending_updates": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
        }
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        return {
            "configured": False,
            "error": str(e),
        }


@router.post("/webhook/set")
async def set_webhook(
    webhook_url: str, 
    device_id: Optional[str] = Header(None, alias="X-Device-ID")
):
    """
    Set Telegram webhook URL.
    Call this once after deploying to production.
    
    Example:
    POST /api/v1/telegram/webhook/set?webhook_url=https://jasper-trades.onrender.com/telegram/webhook
    """
    from app.services.telegram_bot_service import telegram_bot_service
    
    if not telegram_bot_service or not telegram_bot_service.bot:
        raise HTTPException(status_code=503, detail="Bot service not initialized")

    try:
        # Set webhook on Telegram
        await telegram_bot_service.bot.set_webhook(url=webhook_url)
        
        logger.info(f"Telegram webhook set to: {webhook_url}")
        
        return {
            "success": True,
            "webhook_url": webhook_url,
            "message": "Webhook configured successfully"
        }
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/delete")
async def delete_webhook():
    """
    Delete Telegram webhook (switch back to polling mode).
    Use this for local development.
    """
    from app.services.telegram_bot_service import telegram_bot_service
    
    if not telegram_bot_service or not telegram_bot_service.bot:
        raise HTTPException(status_code=503, detail="Bot service not initialized")

    try:
        await telegram_bot_service.bot.delete_webhook()
        
        logger.info("Telegram webhook deleted (switching to polling mode)")
        
        return {
            "success": True,
            "message": "Webhook deleted successfully"
        }
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/list")
async def list_telegram_users(db: AsyncSession = Depends(get_db)):
    """List all verified Telegram users"""
    try:
        result = await db.execute(
            select(TelegramUser).where(TelegramUser.is_verified == True)
        )
        users = result.scalars().all()
        
        return {
            "count": len(users),
            "users": [
                {
                    "device_id": user.device_id[:8] + "***",
                    "chat_id": user.chat_id[:5] + "***",
                    "verified": user.is_verified,
                    "last_active": user.last_active_at.isoformat() if user.last_active_at else None,
                }
                for user in users
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))