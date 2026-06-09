"""
Notify API - Multi-channel notifications
"""
from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, EmailStr
import structlog

from app.services.notify_service import notify_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/notify", tags=["Multi-Channel Notifications"])


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


@router.post("/configure/discord")
async def configure_discord(config: DiscordConfig):
    """Configure Discord webhook"""
    notify_service.configure_discord(config.webhook_url, config.enabled)
    return {"status": "configured", "channel": "discord"}


@router.post("/configure/slack")
async def configure_slack(config: SlackConfig):
    """Configure Slack webhook"""
    notify_service.configure_slack(config.webhook_url, config.enabled)
    return {"status": "configured", "channel": "slack"}


@router.post("/configure/email")
async def configure_email(config: EmailConfig):
    """Configure Email SMTP"""
    notify_service.configure_email(
        smtp_server=config.smtp_server,
        smtp_port=config.smtp_port,
        username=config.username,
        password=config.password,
        from_email=config.from_email,
        to_emails=config.to_emails,
        enabled=config.enabled,
    )
    return {"status": "configured", "channel": "email"}


@router.post("/configure/telegram")
async def configure_telegram(config: TelegramConfig):
    """Configure Telegram bot"""
    notify_service.configure_telegram(config.bot_token, config.chat_id, config.enabled)
    return {"status": "configured", "channel": "telegram"}


@router.post("/send/all")
async def send_to_all(
    title: str = Body(...),
    message: str = Body(...),
):
    """Send notification to all enabled channels"""
    result = await notify_service.send_all_channels(title, message)
    return result


@router.post("/test")
async def test_all_channels():
    """Test all configured channels"""
    title = "🧪 Jasper Trades Test"
    message = (
        "Testing notification channels...\n\n"
        "If you received this, your notification is working correctly!\n\n"
        "Channels:\n"
        "• Discord ✓\n"
        "• Slack ✓\n"
        "• Email ✓\n"
        "• Telegram ✓"
    )
    
    result = await notify_service.send_all_channels(title, message)
    return {
        "status": "test_complete",
        "channels_sent": result.get("channels_sent", 0),
    }


@router.get("/status")
async def get_notify_status():
    """Get notification service status"""
    return notify_service.get_status()