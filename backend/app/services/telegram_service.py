"""
Telegram Notification Service
Sends trade notifications to user's Telegram chat

All messages are sent from "Jasper Trades" bot
"""
import httpx
import structlog
import os
from typing import Optional, Dict, List
from pathlib import Path
import json

logger = structlog.get_logger(__name__)


class TelegramService:
    """
    Telegram notification service using Bot API.
    
    Architecture:
    - Single bot token configured via environment variable (TELEGRAM_BOT_TOKEN)
    - Each user provides their chat ID via settings page
    - Bot sends personalized messages to each user's chat ID
    
    Setup:
    1. Create bot via @BotFather on Telegram
    2. Set TELEGRAM_BOT_TOKEN in Render environment variables
    3. Users enter their chat ID in settings page
    4. Users verify chat ID by receiving a code from the bot
    
    How users get their chat ID:
    1. Start conversation with bot on Telegram
    2. Send /start
    3. Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
    4. Find chat ID in the response
    """

    def __init__(self):
        # Global bot token from environment (set once on Render)
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.enabled = bool(self.bot_token)
        
        # User-specific chat ID stored in database
        self.user_chat_ids: Dict[str, str] = {}  # device_id -> chat_id mapping
        
        if self.enabled:
            logger.info(f"Telegram Service initialized (bot token configured)")
        else:
            logger.warning("Telegram Service disabled - no TELEGRAM_BOT_TOKEN set")

    def register_user(self, device_id: str, chat_id: str):
        """Register a user's chat ID for notifications"""
        self.user_chat_ids[device_id] = chat_id
        logger.info(f"Registered Telegram chat {chat_id} for device {device_id}")

    def unregister_user(self, device_id: str):
        """Unregister a user's chat ID"""
        if device_id in self.user_chat_ids:
            del self.user_chat_ids[device_id]
            logger.info(f"Unregistered Telegram for device {device_id}")

    def get_chat_id(self, device_id: str) -> Optional[str]:
        """Get chat ID for a specific user"""
        return self.user_chat_ids.get(device_id)

    async def send_message(self, chat_id: str, message: str, title: str = None, parse_mode: str = "Markdown") -> bool:
        """Send Telegram message to a specific chat ID
        
        Args:
            chat_id: User's Telegram chat ID
            message: Message content
            title: Optional title (will be bolded)
            parse_mode: Message formatting (default: Markdown)
        """
        if not self.enabled or not self.bot_token or not chat_id:
            logger.debug("Telegram notifications disabled or not configured")
            return False

        try:
            # Format message with title if provided
            if title:
                full_message = f"*{title}*\n\n{message}"
            else:
                full_message = message

            # Send to Telegram Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": full_message,
                        "parse_mode": parse_mode
                    }
                )

                if response.status_code == 200:
                    logger.info(f"Telegram sent to chat {chat_id[:5]}***")
                    return True
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    return False

        except httpx.ConnectError as e:
            logger.warning(f"Telegram API not reachable: {e}")
            return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_verification_code(self, chat_id: str, code: str, expires_minutes: int = 10) -> bool:
        """Send verification code to a chat ID"""
        title = "🔐 VERIFICATION CODE"
        message = (
            f"Your Jasper Trades verification code:\n\n"
            f"*{code}*\n\n"
            f"Expires in {expires_minutes} minutes\n\n"
            f"Enter this code in the app to complete verification."
        )
        return await self.send_message(chat_id, message, title)

    async def send_welcome_message(self, chat_id: str, summary_time: str = "8:00 PM WAT") -> bool:
        """Send welcome message when user first connects."""
        message = (
            f"🔊 *Jasper Trades*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Telegram notifications are working!\n\n"
            f"You will now receive:\n"
            f"• Trade executions\n"
            f"• Trade closures (with PnL)\n"
            f"• Daily summaries at {summary_time}\n"
            f"• System alerts\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Jasper Trades AI"
        )
        return await self.send_message(chat_id, message)

    async def notify_trade_executed(self, chat_id: str, trade: Dict) -> bool:
        """Send trade execution notification"""
        title = "🔔 TRADE EXECUTED"

        message = (
            f"{trade.get('action', 'BUY')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${trade.get('price', 0):.2f}\n"
            f"💵 Total: ${trade.get('total', 0):.2f}\n"
            f"🤖 Agent: {trade.get('agent', 'AI')}\n"
            f"📈 Type: {trade.get('order_type', 'MARKET')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {trade.get('timestamp', 'Now')}"
        )

        return await self.send_message(chat_id, message, title)

    async def notify_trade_closed(self, chat_id: str, trade: Dict) -> bool:
        """Send trade closed/notification with PnL"""
        pnl = trade.get('pnl', 0)
        pnl_percent = trade.get('pnl_percent', 0)

        # Color based on outcome
        if pnl > 0:
            emoji = "✅"
            outcome = "WIN"
        elif pnl < 0:
            emoji = "❌"
            outcome = "LOSS"
        else:
            emoji = "➖"
            outcome = "BREAKEVEN"

        title = f"{emoji} TRADE CLOSED - {outcome}"

        message = (
            f"{trade.get('action', 'SELL')} {trade.get('shares', 0)} {trade.get('symbol', 'UNKNOWN')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Entry: ${trade.get('entry_price', 0):.2f}\n"
            f"💰 Exit: ${trade.get('exit_price', 0):.2f}\n"
            f"📊 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)\n"
            f"⏱ Hold: {trade.get('hold_duration', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {trade.get('timestamp', 'Now')}"
        )

        return await self.send_message(chat_id, message, title)

    async def send_daily_summary(self, chat_id: str, summary_data: Dict) -> bool:
        """Send daily summary notification."""
        title = "📊 DAILY SUMMARY"
        message = (
            f"📅 {summary_data.get('date', 'Today')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Total PnL: ${summary_data.get('total_pnl', 0):+,.2f}\n"
            f"📈 Return: {summary_data.get('total_pnl_percent', 0):+,.2f}%\n"
            f"📊 Win Rate: {summary_data.get('win_rate', 0):.1f}%\n"
            f"🎯 Trades: {summary_data.get('total_trades', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Jasper Trades AI"
        )
        return await self.send_message(chat_id, message, title)

    async def test_connection(self, chat_id: str) -> bool:
        """Test Telegram connection with a test message"""
        test_message = (
            "🔊 *Jasper Trades Test*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✅ Telegram notifications are working!\n\n"
            "You will now receive:\n"
            "• Trade executions\n"
            "• Trade closures (with PnL)\n"
            "• Daily summaries\n"
            "• System alerts\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 Jasper Trades AI"
        )

        success = await self.send_message(chat_id, test_message)

        if success:
            logger.info(f"Telegram test message sent to {chat_id[:5]}***")
        else:
            logger.warning(f"Telegram test message failed for {chat_id[:5]}***")

        return success


# Singleton instance
telegram_service = TelegramService()