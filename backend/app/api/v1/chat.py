"""
WhatsApp Chat + Configuration API
Receive messages, process with AI, send responses
Configure and test WhatsApp notifications
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import structlog
from datetime import datetime

from app.database import get_db
from app.models import ChatMessage
from app.services.whatsapp_service import whatsapp_service
from app.services.chat_ai import get_chat_ai

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


class WebhookMessage(BaseModel):
    """Incoming WhatsApp message from OpenWA webhook."""
    phone: str
    message: str
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    success: bool = True


class WhatsAppConfig(BaseModel):
    phone_number: str
    enabled: bool = True
    openwa_url: Optional[str] = "http://localhost:3001"


class TestMessageRequest(BaseModel):
    message: str = "Test message from Jasper Trades"


@router.post("/webhook")
async def whatsapp_webhook(
    data: WebhookMessage,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive incoming WhatsApp message from OpenWA.
    This endpoint is called by OpenWA when a message arrives.
    """
    logger.info(f"WhatsApp webhook received", phone=data.phone, message=data.message[:50])

    try:
        # Store incoming message
        chat_msg = ChatMessage(
            phone_number=data.phone,
            message=data.message,
            direction="incoming",
            message_type="text",
        )
        db.add(chat_msg)
        await db.commit()

        # Get AI response
        chat_ai = get_chat_ai(db)
        response_text = await chat_ai.handle_message(data.phone, data.message)

        # Store AI response
        ai_msg = ChatMessage(
            phone_number=data.phone,
            message=response_text,
            direction="outgoing",
            message_type="ai_response",
            intent=chat_ai._detect_intent(data.message),
        )
        db.add(ai_msg)
        await db.commit()

        # Send response via WhatsApp
        success = await whatsapp_service.send_message(data.phone, response_text)

        if success:
            return {"success": True, "response": response_text}
        else:
            logger.error("Failed to send WhatsApp response")
            return {"success": False, "error": "Failed to send message"}

    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/history")
async def get_chat_history(
    phone: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get chat history."""
    from sqlalchemy import select

    query = select(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(limit)

    if phone:
        query = query.where(ChatMessage.phone_number == phone)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    return {
        "messages": [
            {
                "id": m.id,
                "phone": m.phone_number,
                "message": m.message,
                "direction": m.direction,
                "type": m.message_type,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "count": len(messages),
    }


@router.post("/send")
async def send_chat_message(
    phone: str,
    message: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a WhatsApp message (manual or programmatic)."""
    try:
        # Store message
        chat_msg = ChatMessage(
            phone_number=phone,
            message=message,
            direction="outgoing",
            message_type="text",
        )
        db.add(chat_msg)
        await db.commit()

        # Send via WhatsApp service
        success = await whatsapp_service.send_message(phone, message)

        return {
            "success": success,
            "message": "Message sent" if success else "Failed to send",
        }

    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """Get WhatsApp configuration."""
    return whatsapp_service.get_status()


@router.delete("/clear/{phone}")
async def clear_chat_history(
    phone: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear chat history for a phone number."""
    from sqlalchemy import delete

    stmt = delete(ChatMessage).where(ChatMessage.phone_number == phone)
    await db.execute(stmt)
    await db.commit()

    return {"success": True, "message": f"Cleared history for {phone}"}


# ============ Legacy Configuration Endpoints ============

@router.get("/status")
async def get_whatsapp_status():
    """Get WhatsApp notification status"""
    return whatsapp_service.get_status()


@router.post("/configure")
async def configure_whatsapp(config: WhatsAppConfig):
    """Configure WhatsApp (legacy - use /api/v1/settings/notifications/whatsapp/configure)"""
    if not config.phone_number or len(config.phone_number) < 7:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    whatsapp_service.configure(
        phone_number=config.phone_number,
        enabled=config.enabled,
        openwa_url=config.openwa_url
    )

    return {
        "success": True,
        "message": "WhatsApp configured successfully",
        "phone_number": whatsapp_service.phone_number[:5] + "***"
    }


@router.post("/test")
async def test_whatsapp(request: Optional[TestMessageRequest] = None):
    """Send test WhatsApp message"""
    if not whatsapp_service.enabled or not whatsapp_service.phone_number:
        raise HTTPException(status_code=400, detail="WhatsApp not configured")

    success = await whatsapp_service.test_connection()
    if success:
        return {"success": True, "message": "Test message sent!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test message")


@router.post("/disable")
async def disable_whatsapp():
    """Disable WhatsApp notifications"""
    whatsapp_service.configure(phone_number=whatsapp_service.phone_number, enabled=False)
    return {"success": True, "message": "WhatsApp notifications disabled"}


@router.post("/enable")
async def enable_whatsapp():
    """Enable WhatsApp notifications"""
    if not whatsapp_service.phone_number:
        raise HTTPException(status_code=400, detail="No phone number configured")

    whatsapp_service.configure(phone_number=whatsapp_service.phone_number, enabled=True)
    return {"success": True, "message": "WhatsApp notifications enabled"}