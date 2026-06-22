# Telegram Bot Setup for Jasper Trades

Complete step-by-step guide to build a Telegram bot for notifications and two-way chat features.

## 📋 Overview

This guide covers:
1. **Bot Creation** - Register bot with Telegram via BotFather
2. **Backend Implementation** - Bot polling service and webhook handlers
3. **Two-Way Chat** - Process user commands and send AI responses
4. **Notifications** - Trade alerts, daily summaries, system messages
5. **Testing & Deployment** - Local testing and production deployment

---

## 🚀 Step 1: Create Telegram Bot

### 1.1 Open BotFather

1. Open Telegram app
2. Search for `@BotFather` (official bot with blue checkmark)
3. Start chat with bot

### 1.2 Create New Bot

1. Send command: `/newbot`
2. BotFather asks for bot name:
   - Example: `Jasper Trades`
3. BotFather asks for username:
   - Must end in `bot`
   - Example: `jasper_trades_bot` or `JasperTradesAI_bot`
4. BotFather responds with:
   ```
   Done! Congratulations on your new bot.
   You can find it at t.me/jasper_trades_bot

   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

   For a description of the Bot API, see: https://core.telegram.org/bots/api
   ```

### 1.3 Save Bot Token

**CRITICAL**: Copy the bot token (e.g., `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

Add to `.env` file:
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 1.4 Configure Bot Settings

Send these commands to BotFather:

1. `/setdescription` - Set bot description
   ```
   AI-powered trading notifications and chat for Jasper Trades platform
   ```

2. `/setabouttext` - Set about text
   ```
   Jasper Trades AI - Real-time trading signals, portfolio tracking, and 2-way chat
   ```

3. `/setuserpic` - Upload bot profile picture (optional)
   - Send a 512x512px square image

4. `/setinline` - Disable inline mode (send `Disable`)

---

## 🛠️ Step 2: Install Required Dependencies

### 2.1 Add python-telegram-bot to requirements

Edit `backend/requirements.txt`:

```txt
# Add these lines
python-telegram-bot==21.0  # Async Telegram Bot API
apscheduler==3.10.4        # For scheduled daily summaries
```

### 2.2 Install packages

```bash
cd backend
pip install -r requirements.txt
```

---

## 🏗️ Step 3: Build Telegram Bot Service

Create `backend/app/services/telegram_bot_service.py`:

```python
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
from typing import Optional, Dict
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

    def _register_handlers):
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
        """Handle /status command"""
        chat_id = update.effective_chat.id
        
        # TODO: Fetch from backend API
        # For now, show placeholder
        message = "📊 *Account Status*\n\nLoading..."
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        # TODO: Implement portfolio fetch
        message = "💼 *Portfolio*\n\nLoading..."
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        # TODO: Implement trades fetch
        message = "📜 *Recent Trades*\n\nLoading..."
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        message = "⚙️ *Notification Settings*\n\nConfigure what you want to receive"
        # TODO: Add inline keyboard for settings
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_verify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - verify chat ID"""
        chat_id = str(update.effective_chat.id)
        
        message = (
            f"🔐 *Chat ID Verification*\n\n"
            f"Your Telegram Chat ID: `{chat_id}`\n\n"
            f"Copy this ID and paste it in the Jasper Trades app:\n"
            f"`Settings → Telegram → Enter Chat ID`\n\n"
            f"Or use the command: `/verify {chat_id}`"
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

        # TODO: Call backend AI chat endpoint
        # response = await call_backend_chat_api(user_message, chat_id)
        
        # Placeholder response
        response = f"Thanks for your message: '{user_message}'\n\nAI response coming soon..."

        await update.message.reply_text(response, parse_mode="Markdown")

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
            logger.info(f"Trade notification sent to {chat_id}")
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
            logger.info(f"Trade closure sent to {chat_id}")
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
            logger.info(f"Daily summary sent to {chat_id}")
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
```

---

## 🔌 Step 4: Create Bot Startup Integration

Create `backend/app/main.py` updates:

Add to imports:
```python
from app.services.telegram_bot_service import get_telegram_bot_service, telegram_bot_service
```

Add to lifespan function (in the startup section):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...

    # Initialize Telegram bot
    if settings.TELEGRAM_BOT_TOKEN:
        bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
        await bot_service.initialize()
        
        # Start polling in background task
        asyncio.create_task(bot_service.start_polling())
        logger.info("Telegram Bot started (long polling)")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set - Telegram bot disabled")

    yield  # Application runs

    # Shutdown
    if telegram_bot_service and telegram_bot_service.running:
        await telegram_bot_service.stop_polling()
        logger.info("Telegram Bot stopped")
```

---

## 🌐 Step 5: Create Webhook Endpoint (For Production)

Create `backend/app/api/v1/telegram_webhook.py`:

```python
"""
Telegram Webhook Endpoint
Receives updates from Telegram instead of polling
"""
from fastapi import APIRouter, Request, HTTPException
from telegram import Update
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.
    Telegram sends updates here when configured for webhooks.
    """
    try:
        # Get raw JSON from request
        data = await request.json()
        logger.info(f"Telegram webhook received: {data.get('update_id')}")

        # TODO: Pass to bot service for processing
        # from app.services.telegram_bot_service import telegram_bot_service
        # update = Update.de_json(data)
        # await telegram_bot_service.process_update(update)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/webhook/info")
async def get_webhook_info():
    """Get current webhook configuration"""
    # TODO: Call Bot API to get webhook info
    # response = await bot.get_webhook_info()
    return {
        "webhook_url": "Not configured",
        "pending_updates": 0,
    }
```

Add route to `main.py`:
```python
from app.api.v1 import telegram_webhook
app.include_router(telegram_webhook.router)
```

---

## 📱 Step 6: Get User Chat ID

Users need to verify their chat ID to receive notifications.

### Method 1: In-Bot Command

Users message the bot and send:
```
/verify
```

Bot responds with their chat ID.

### Method 2: Backend API

Create endpoint to submit chat ID:

```python
# In telegram_settings.py (already exists)
@router.post("/verify/submit")
async def submit_chat_id(chat_id: str, device_id: str = Header(...)):
    """Submit Telegram chat ID for verification"""
    # Store in database
    pass
```

---

## 🧪 Step 7: Test Locally

### 7.1 Run backend with bot token

```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 7.2 Test bot commands

1. Open Telegram
2. Go to your bot: `t.me/jasper_trades_bot`
3. Click "START"
4. Try commands:
   - `/start`
   - `/help`
   - `/verify`

### 7.3 Check logs

You should see:
```
INFO - Telegram Bot initialized: @jasper_trades_bot (ID: 123456789)
INFO - Starting Telegram Bot polling...
INFO - Message from @username: /start...
```

---

## 🚀 Step 8: Production Deployment

### 8.1 Use Webhooks Instead of Polling

For production (Render, Vercel, etc.), use webhooks:

1. Set webhook URL:
```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://jasper-trades.onrender.com/telegram/webhook"
```

2. Remove polling from `main.py`:
```python
# Don't start polling in production
# Just initialize bot for sending messages
if settings.TELEGRAM_BOT_TOKEN:
    bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
    await bot_service.initialize()
    logger.info("Telegram Bot initialized (webhook mode)")
```

### 8.2 Environment Variables on Render

Add to Render dashboard:
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## 📊 Step 9: Integrate with Trading System

### 9.1 Send Trade Notifications

In your trade execution service:

```python
from app.services.telegram_bot_service import get_telegram_bot_service

async def execute_trade(trade_data: dict, device_id: str):
    # ... execute trade ...

    # Get user's chat_id from database
    chat_id = await get_user_chat_id(device_id)

    if chat_id:
        bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
        await bot_service.send_trade_notification(chat_id, trade_data)
```

### 9.2 Daily Summary Scheduler

Create `backend/app/schedulers/telegram_daily_summary.py`:

```python
"""Daily summary scheduler for Telegram"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()


async def send_daily_summaries():
    """Check all users and send daily summaries"""
    # TODO: Query database for users with daily_summary_enabled=True
    # TODO: For each user, fetch today's trades and compute summary
    # TODO: Send via bot_service.send_daily_summary()
    logger.info("Daily summary job executed")


def start_summary_scheduler():
    """Start daily summary scheduler (8 PM WAT = 19:00 UTC)"""
    scheduler.add_job(
        send_daily_summaries,
        CronTrigger(hour=19, minute=0),  # 8 PM WAT (UTC+1)
        id="telegram_daily_summary"
    )
    scheduler.start()
    logger.info("Telegram daily summary scheduler started (8 PM WAT)")


def stop_summary_scheduler():
    """Stop scheduler"""
    scheduler.shutdown()
```

Add to `main.py` startup:
```python
from app.schedulers.telegram_daily_summary import start_summary_scheduler
start_summary_scheduler()
```

---

## ✅ Verification Checklist

- [ ] Bot created via BotFather
- [ ] Bot token saved in `.env`
- [ ] `python-telegram-bot` installed
- [ ] Bot service created
- [ ] Handlers registered for commands
- [ ] Local testing successful
- [ ] Users can send `/start` and get response
- [ ] Chat ID verification working
- [ ] Trade notifications integrated
- [ ] Daily summary scheduled
- [ ] Production webhook configured (if deploying)

---

## 🔧 Troubleshooting

### Bot not responding

1. Check bot token is correct
2. Verify bot is running: check logs for "Telegram Bot started"
3. Ensure user hasn't blocked the bot

### Polling errors

- Rate limit: Telegram allows 30 messages/sec
- Long polling timeout: Set to 30s minimum

### Webhook not working

1. Must be HTTPS
2. Port must be 443, 80, 88, or 8443
3. Check with: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

---

## 📚 Resources

- [Telegram Bot API Docs](https://core.telegram.org/bots/api)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [BotFather Commands](https://core.telegram.org/bots#6-botfather)