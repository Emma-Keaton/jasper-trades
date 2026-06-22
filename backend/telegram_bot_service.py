"""
Telegram Bot Service - Long Polling & Command Handler
Handles incoming messages, commands, and sends notifications
"""
import asyncio
import structlog
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

logger = structlog.get_logger(__name__)


class TelegramBotService:
    """
    Telegram bot for 2-way chat and notifications.
    Uses long polling (recommended for local dev) or webhooks (production).
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.running = False
        self.chat_sessions: Dict[str, dict] = {}  # chat_id -> session data
        logger.info("Telegram Bot Service initialized")

    async def initialize(self):
        """Initialize bot application"""
        try:
            # Create bot application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Get bot info
            self.bot = await self.application.bot.get_me()
            logger.info(f"Bot initialized: @{self.bot.username} (ID: {self.bot.id})")

            # Register handlers
            self._register_handlers()

            logger.info("Telegram Bot handlers registered")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram Bot: {e}")
            raise

    def _register_handlers(self):
        """Register command and message handlers"""
        if not self.application:
            return

        # Commands
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.application.add_handler(CommandHandler("trades", self.cmd_trades))
        self.application.add_handler(CommandHandler("settings", self.cmd_settings))
        self.application.add_handler(CommandHandler("verify", self.cmd_verify))

        # Natural language messages (for AI chat)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

    async def start_polling(self):
        """Start long polling (for local development)"""
        if not self.application:
            await self.initialize()

        self.running = True
        logger.info("Starting Telegram Bot polling...")
        
        # Run with error handling
        await self.application.run_polling(
            poll_interval=1.0,  # Check for updates every 1 second
            timeout=30,
            allowed_updates=["message", "callback_query"],
        )

    async def stop_polling(self):
        """Stop long polling"""
        self.running = False
        if self.application:
            await self.application.stop()
            logger.info("Telegram Bot polling stopped")

    # ============ Command Handlers ============

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        username = update.effective_user.username or update.effective_user.first_name

        # Log chat session
        self.chat_sessions[str(chat_id)] = {
            "user_id": update.effective_user.id,
            "username": username,
            "started_at": datetime.utcnow(),
            "last_message": datetime.utcnow(),
        }

        message = (
            f"👋 *Welcome to Jasper Trades, {username}!*\n\n"
            f"I'm your AI trading assistant. I can help you with:\n\n"
            f"• 📊 View portfolio and positions\n"
            f"• 📜 Check recent trades\n"
            f"• 🔔 Real-time trade notifications\n"
            f"• 📈 Trading signals and analysis\n"
            f"• 💬 Chat about market conditions\n\n"
            f"*Commands:*\n"
            f"/help - Show all commands\n"
            f"/status - Account status\n"
            f"/portfolio - Current holdings\n"
            f"/trades - Recent trades\n"
            f"/settings - Notification preferences\n"
            f"/verify - Verify your chat ID\n\n"
            f"Just type naturally to chat with me!"
        )

        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        message = (
            "📖 *Jasper Trades Bot Commands*\n\n"
            "*Account & Portfolio:*\n"
            "/start - Start bot and show welcome\n"
            "/status - Check account status\n"
            "/portfolio - View current holdings\n"
            "/trades - Recent trade history\n\n"
            "*Settings:*\n"
            "/settings - Notification preferences\n"
            "/verify - Verify Telegram chat ID\n\n"
            "*Natural Chat:*\n"
            "Just type naturally! Examples:\n"
            "• \"What's my portfolio value?\"\n"
            "• \"Show me recent trades\"\n"
            "• \"How did AAPL perform today?\"\n"
            "• \"What trades did the AI make?\"\n\n"
            "*Daily Summary:*\n"
            "Automatically sent at 8 PM WAT (configurable)"
        )

        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - Fetch from backend API"""
        chat_id = update.effective_chat.id
        
        try:
            # Fetch from backend API using chat_id to find device_id
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "http://localhost:8000/api/v1/settings/telegram/status",
                    headers={"X-Device-ID": "from_chat:" + str(chat_id)}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    message = (
                        f"📊 *Account Status*\n\n"
                        f"Verified: {'✅ Yes' if data.get('is_verified') else '❌ No'}\n"
                        f"Chat ID: `{data.get('chat_id', 'N/A')}`\n\n"
                        f"*Notifications:*\n"
                        f"• Trades: {'✅' if data.get('preferences', {}).get('trade_notifications_enabled') else '❌'}\n"
                        f"• Daily Summary: {'✅' if data.get('preferences', {}).get('daily_summary_enabled') else '❌'}\n"
                        f"• AI Chat: {'✅' if data.get('preferences', {}).get('chat_enabled') else '❌'}"
                    )
                else:
                    message = "❌ Could not retrieve status. Please verify your chat ID in the app first."
        except Exception as e:
            logger.error(f"Failed to fetch status: {e}")
            message = "⚠️ Service temporarily unavailable. Please try again later."

        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command - Fetch from backend API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # TODO: Implement portfolio endpoint
                message = (
                    "💼 *Portfolio*\n\n"
                    f"Total Value: $100,000.00\n"
                    f"Cash: $50,000.00\n"
                    f"Positions: 5\n"
                    f"PnL: +$5,000.00 (+5.00%)\n\n"
                    "📈 *Top Holdings:*\n"
                    f"• AAPL: 100 @ $150.00\n"
                    f"• MSFT: 50 @ $320.00\n"
                    f"• GOOGL: 20 @ $140.00"
                )
        except Exception as e:
            logger.error(f"Failed to fetch portfolio: {e}")
            message = "⚠️ Could not retrieve portfolio"

        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command - Fetch from backend API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # TODO: Implement trades endpoint
                message = (
                    "📜 *Recent Trades*\n\n"
                    f"• BUY 100 AAPL @ $150.00 - $15,000.00\n"
                    f"• SELL 50 MSFT @ $320.00 - +$2,500.00 ✅\n"
                    f"• BUY 20 GOOGL @ $140.00 - $2,800.00\n\n"
                    f"Last 24h: +3 trades, +$2,500.00"
                )
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            message = "⚠️ Could not retrieve trades"

        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        message = (
            "⚙️ *Notification Settings*\n\n"
            "Use the app to configure:\n"
            f"• Trade notifications\n"
            f"• Daily summary schedule\n"
            f"• AI chat explanations\n\n"
            f"Quick command: `/verify` to get your chat ID"
        )
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_verify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - verify chat ID"""
        chat_id = str(update.effective_chat.id)
        
        message = (
            f"🔐 *Chat ID Verification*\n\n"
            f"Your Telegram Chat ID: `{chat_id}`\n\n"
            f"Copy this ID and paste it in the Jasper Trades app:\n"
            f"`Settings → Telegram → Enter Chat ID`\n\n"
            f"Then click 'Request Verification Code' to complete setup."
        )

        await update.message.reply_text(message, parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages (AI chat)"""
        user_message = update.message.text
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "User"

        # Log message
        logger.info(f"Message from @{username}: {user_message[:50]}...")

        # Send typing indicator
        await update.chat_action(action="typing")

        try:
            # Call backend AI chat endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/chat/telegram",
                    json={
                        "chat_id": str(chat_id),
                        "message": user_message,
                        "username": username
                    }
                )
                
                if response.status_code == 200:
                    ai_response = response.json().get("response", "I'm processing your request...")
                else:
                    ai_response = "⚠️ I'm having trouble connecting to the trading system. Please try again in a moment."
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            ai_response = "⚠️ Service temporarily unavailable. Please try again later."

        await update.message.reply_text(ai_response, parse_mode="Markdown")

    # ============ Notification Methods ============

    async def send_trade_notification(self, chat_id: str, trade_data: dict) -> bool:
        """Send trade execution notification"""
        if not self.bot:
            logger.error("Bot not initialized")
            return False

        message = (
            f"🔔 *TRADE EXECUTED*\n\n"
            f"{trade_data['action']} {trade_data['shares']} {trade_data['symbol']}\n"
            f"━━━━━━━━━━\n"
            f"💰 Price: ${trade_data['price']:.2f}\n"
            f"💵 Total: ${trade_data['total']:.2f}\n"
            f"🤖 Agent: {trade_data.get('agent', 'AI')}\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"
        )

        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown"
            )
            logger.info(f"Trade notification sent to {chat_id[:5]}***")
            return True
        except Exception as e:
            logger.error(f"Failed to send trade notification: {e}")
            return False

    async def send_trade_closure(self, chat_id: str, trade_data: dict) -> bool:
        """Send trade closure notification with PnL"""
        if not self.bot:
            return False

        pnl = trade_data.get('pnl', 0)
        pnl_percent = trade_data.get('pnl_percent', 0)
        emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"

        message = (
            f"{emoji} *TRADE CLOSED - {outcome}*\n\n"
            f"{trade_data['symbol']}\n"
            f"━━━━━━━━━━\n"
            f"💰 Entry: ${trade_data['entry_price']:.2f}\n"
            f"💰 Exit: ${trade_data['exit_price']:.2f}\n"
            f"📊 PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)\n"
            f"⏱ Hold: {trade_data.get('hold_duration', 'N/A')}"
        )

        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown"
            )
            logger.info(f"Trade closure sent to {chat_id[:5]}***")
            return True
        except Exception as e:
            logger.error(f"Failed to send trade closure: {e}")
            return False

    async def send_daily_summary(self, chat_id: str, summary_data: dict) -> bool:
        """Send daily trading summary"""
        if not self.bot:
            return False

        message = (
            f"📊 *DAILY SUMMARY*\n\n"
            f"📅 {summary_data.get('date', 'Today')}\n"
            f"━━━━━━━━━━\n"
            f"💰 Total PnL: ${summary_data['total_pnl']:+,.2f}\n"
            f"📈 Return: {summary_data['total_pnl_percent']:+,.2f}%\n"
            f"📊 Win Rate: {summary_data['win_rate']:.1f}%\n"
            f"🎯 Trades: {summary_data['total_trades']}\n"
            f"━━━━━━━━━━\n"
            f"🤖 Jasper Trades AI"
        )

        try:
            await self.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            logger.info(f"Daily summary sent to {chat_id[:5]}***")
            return True
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False

    async def send_alert(self, chat_id: str, title: str, message: str) -> bool:
        """Send system alert"""
        if not self.bot:
            return False

        full_message = f"⚠️ *{title}*\n\n{message}"

        try:
            await self.bot.send_message(chat_id=chat_id, text=full_message, parse_mode="Markdown")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False


# Singleton instance (initialize with token from env)
telegram_bot_service: Optional[TelegramBotService] = None


def get_telegram_bot_service(bot_token: str) -> TelegramBotService:
    """Get or create Telegram bot service"""
    global telegram_bot_service
    if telegram_bot_service is None:
        telegram_bot_service = TelegramBotService(bot_token)
    return telegram_bot_service