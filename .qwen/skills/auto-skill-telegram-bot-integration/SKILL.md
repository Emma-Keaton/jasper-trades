---
name: telegram-bot-integration
description: Complete Telegram bot integration for trading notifications and 2-way chat with long polling and webhook support
source: auto-skill
extracted_at: '2026-06-19T19:39:59.167Z'
---

# Telegram Bot Integration for Trading Applications

Complete procedure for implementing a Telegram bot for trading notifications and two-way chat, replacing WhatsApp/OpenWA dependencies.

## Overview

This skill covers:
- Bot creation and configuration via BotFather
- Backend service implementation with python-telegram-bot
- Command handlers for user interactions
- Trade execution notifications
- Two-way AI-powered chat
- Long polling (development) and webhook (production) modes
- Database integration for user verification and preferences

## Step-by-Step Procedure

### 1. Create Telegram Bot via BotFather

**Commands to send to @BotFather:**

1. `/newbot` - Create new bot
2. Choose name: `Jasper Trades` (or your app name)
3. Choose username: `jasper_trades_bot` (must end with `bot`)
4. **Save the bot token** (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**Optional configuration:**
- `/setdescription` - Set bot description
- `/setabouttext` - Set about text  
- `/setuserpic` - Upload profile picture (512x512px)

### 2. Install Dependencies

Add to `requirements.txt`:
```txt
python-telegram-bot==21.0
apscheduler==3.10.4  # For scheduled daily summaries
```

Install:
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Add to `.env`:
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

Add to config.py:
```python
TELEGRAM_BOT_TOKEN: Optional[str] = None
```

### 4. Create Telegram Bot Service

Create `backend/app/services/telegram_bot_service.py`:

**Key components:**
- Singleton pattern for bot instance
- Async initialization with `Application.builder()`
- Command handlers: `/start`, `/help`, `/status`, `/portfolio`, `/trades`, `/settings`, `/verify`
- Message handler for natural language chat
- Notification methods: `send_trade_notification()`, `send_trade_closure()`, `send_daily_summary()`, `send_alert()`

**Example structure:**
```python
class TelegramBotService:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.running = False
        
    async def initialize(self):
        self.application = Application.builder().token(self.bot_token).build()
        self.bot = await self.application.bot.get_me()
        self._register_handlers()
        
    def _register_handlers(self):
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
    
    async def start_polling(self):
        await self.application.run_polling(poll_interval=1.0, timeout=30)
```

### 5. Create Webhook Endpoint (Production)

Create `backend/app/api/v1/telegram_webhook.py`:

**Endpoints:**
- `POST /api/v1/telegram/webhook` - Receives updates from Telegram
- `GET /api/v1/telegram/webhook/info` - Get webhook configuration
- `POST /api/v1/telegram/webhook/set` - Set webhook URL
- `POST /api/v1/telegram/webhook/delete` - Switch back to polling

**Key implementation:**
```python
@router.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data)
    await telegram_bot_service.application.process_update(update)
    return {"status": "ok"}
```

### 6. Create AI Chat Endpoint

Create `backend/app/api/v1/telegram_chat.py`:

**Features:**
- Intent detection (portfolio, trades, status, signal, general)
- Backend API integration for real data
- Chat history storage in database
- AI response generation via NVIDIA NIM or other LLM

**Intent detection example:**
```python
def detect_intent(message: str) -> str:
    message_lower = message.lower()
    if "portfolio" in message_lower or "balance" in message_lower:
        return "portfolio"
    if "trade" in message_lower or "bought" in message_lower:
        return "trades"
    return "general"
```

### 7. Update Main Application

**Modify `main.py`:**

**Remove WhatsApp imports:**
```python
# Remove:
from app.services.embedded_openwa import embedded_openwa, get_embedded_openwa
from app.api.v1 import chat  # WhatsApp chat router
```

**Add Telegram imports:**
```python
from app.api.v1 import telegram_settings
from app.api.v1 import telegram_webhook
from app.api.v1 import telegram_chat
```

**Add bot startup in lifespan:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.TELEGRAM_BOT_TOKEN:
        from app.services.telegram_bot_service import get_telegram_bot_service
        bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
        await bot_service.initialize()
        asyncio.create_task(bot_service.start_polling())
        logger.info(f"Telegram Bot started - @{bot_service.bot.username}")
    
    yield
    
    # Shutdown
    if telegram_bot_service and telegram_bot_service.running:
        await telegram_bot_service.stop_polling()
```

**Register routers:**
```python
app.include_router(telegram_settings.router, prefix="/api/v1", tags=["telegram-settings"])
app.include_router(telegram_webhook.router, tags=["telegram-webhook"])
app.include_router(telegram_chat.router, tags=["telegram-chat"])
```

### 8. Update Trade Notifications

**Modify `trading.py`:**

**Remove WhatsApp import:**
```python
# Remove: from app.services.whatsapp_service import whatsapp_service
```

**Add Telegram notification function:**
```python
async def _send_trade_telegram_notification(trade: Trade, device_id: str, db: AsyncSession):
    from app.services.telegram_bot_service import get_telegram_bot_service
    from app.models import TelegramUser
    from sqlalchemy import select
    
    # Get verified user with notifications enabled
    result = await db.execute(
        select(TelegramUser).where(
            TelegramUser.device_id == device_id,
            TelegramUser.is_verified == True,
            TelegramUser.trade_notifications_enabled == True
        )
    )
    user = result.scalar_one_or_none()
    
    if user:
        trade_data = {
            "action": "BUY" if trade.side == "buy" else "SELL",
            "symbol": trade.symbol,
            "shares": trade.quantity,
            "price": trade.price or 0,
        }
        bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
        await bot_service.send_trade_notification(user.chat_id, trade_data)
```

### 9. Database Models

Ensure `models.py` has `TelegramUser` table:
```python
class TelegramUser(Base):
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(255), nullable=False, unique=True, index=True)
    chat_id = Column(String, nullable=False)
    trade_notifications_enabled = Column(Boolean, default=True)
    daily_summary_enabled = Column(Boolean, default=True)
    summary_time_wat = Column(String, default="20:00")
    chat_enabled = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, nullable=True)
```

### 10. Testing

**Test bot locally:**
```bash
cd backend
python -m uvicorn app.main:app --reload
```

**Test commands:**
1. Open Telegram → `@your_bot_username`
2. Click START or send `/start`
3. Try: `/help`, `/verify`, `/status`
4. Send natural message: "What's my portfolio?"

**Verify in logs:**
```
INFO: Telegram Bot started (long polling mode) - @jasper_trades_bot
INFO: Message from @username: /start...
INFO: Trade notification sent to 12345***
```

### 11. Production Deployment

**For Render/Vercel/Cloud:**

1. **Set webhook instead of polling:**
```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.onrender.com/telegram/webhook"
```

2. **Update main.py to skip polling:**
```python
# Don't start polling in production
if settings.TELEGRAM_BOT_TOKEN:
    bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
    await bot_service.initialize()
    logger.info("Telegram Bot initialized (webhook mode)")
```

3. **Add environment variable to cloud dashboard:**
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-app.onrender.com/telegram/webhook
```

## Key Implementation Patterns

### Notification Flow
1. Trade executed → Save to database
2. Async task triggered → Query `TelegramUser` by device_id
3. Check `is_verified` and `trade_notifications_enabled`
4. Format message with trade details
5. Send via `bot.send_message(chat_id, text, parse_mode="Markdown")`

### Two-Way Chat Flow
1. User sends message → Bot receives via polling/webhook
2. `handle_message()` → Call backend `/api/v1/chat/telegram` endpoint
3. Intent detection → Route to appropriate handler
4. Query database for user data (portfolio, trades, etc.)
5. Generate AI response via LLM
6. Send response back to user

### User Verification Flow
1. User sends `/verify` → Bot returns chat ID
2. User enters chat ID in app Settings → Telegram page
3. App generates verification code → Sends to Telegram
4. User enters code in app → Marks `is_verified = True`
5. Now eligible to receive notifications

## Common Issues & Solutions

**Issue:** Bot not responding
- **Solution:** Check bot token is correct, verify bot is running in logs, ensure user hasn't blocked bot

**Issue:** "Chat not found" error
- **Solution:** User must click START first to activate chat, chat ID format (try positive/negative integer)

**Issue:** Polling not starting
- **Solution:** Check `TELEGRAM_BOT_TOKEN` in correct `.env` file, verify no import errors

**Issue:** Webhook not receiving updates
- **Solution:** Must use HTTPS, check with `getWebhookInfo`, ensure URL is publicly accessible

**Issue:** WhatsApp imports still present
- **Solution:** Search codebase for `whatsapp_service`, `embedded_openwa` and remove/replace all references

## Files Created/Modified

**Created:**
- `backend/app/services/telegram_bot_service.py` - Bot service
- `backend/app/api/v1/telegram_webhook.py` - Webhook endpoints
- `backend/app/api/v1/telegram_chat.py` - AI chat endpoint
- `backend/test_bot_quick.py` - Quick test script

**Modified:**
- `backend/app/main.py` - Bot integration, remove WhatsApp
- `backend/app/api/v1/trading.py` - Replace WhatsApp with Telegram notifications
- `backend/requirements.txt` - Add python-telegram-bot, apscheduler
- `backend/.env` - Add TELEGRAM_BOT_TOKEN
- `backend/app/config.py` - Add TELEGRAM_BOT_TOKEN setting

## Testing Checklist

- [ ] Bot created via BotFather
- [ ] Bot token in `.env`
- [ ] Packages installed
- [ ] Backend starts successfully
- [ ] `/start` command works
- [ ] `/help` shows commands
- [ ] `/verify` returns chat ID
- [ ] Natural language messages get responses
- [ ] Trade notifications send (when trades execute)
- [ ] Production webhook configured (if deploying)

## Migration from WhatsApp

**When replacing WhatsApp/OpenWA:**

1. Remove all `whatsapp_service` imports
2. Remove `embedded_openwa` service
3. Replace notification calls with Telegram equivalents
4. Update chat endpoints to use Telegram
5. Remove OpenWA webhook server (Node.js)
6. Test all flows work with Telegram only
7. Update documentation to reference Telegram instead of WhatsApp