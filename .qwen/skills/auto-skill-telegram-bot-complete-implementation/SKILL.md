---
name: telegram-bot-complete-implementation
description: Complete Telegram bot implementation replacing WhatsApp with proper error handling, real data fetching, and no placeholders
source: auto-skill
extracted_at: '2026-06-19T21:15:00.000Z'
---

# Complete Telegram Bot Implementation (WhatsApp Replacement)

This skill documents the complete implementation of a Telegram bot for trading notifications and 2-way chat, replacing the WhatsApp/OpenWA integration.

## What Changed

### 1. Removed WhatsApp/OpenWA Dependencies
- Deleted all `embedded_openwa` imports and service calls
- Removed `whatsapp_service` imports from API routes
- Commented out old `chat.py` router imports in `main.py`
- Replaced all WhatsApp notification triggers with Telegram

### 2. Created Telegram Bot Service
**File:** `backend/app/services/telegram_bot_service.py`

Key features:
- Uses `python-telegram-bot==21.0` library
- Implements long polling for local development
- Supports webhook mode for production (Render/Vercel)
- Command handlers for: `/start`, `/help`, `/status`, `/portfolio`, `/trades`, `/settings`, `/verify`
- Message handler for natural language AI chat

### 3. Created Telegram API Routes
**Files:**
- `backend/app/api/v1/telegram_settings.py` - Configuration and preferences
- `backend/app/api/v1/telegram_chat.py` - AI chat endpoint for Telegram
- `backend/app/api/v1/telegram_webhook.py` - Webhook handler for production

### 4. Updated Trade Notifications
**File:** `backend/app/api/v1/telegramscheduler.py` (trade execution)

Replaced:
```python
# Old WhatsApp
await whatsapp_service.notify_trade_executed(trade_data)
```

With:
```python
# New Telegram
async def _send_trade_telegram_notification(trade: Trade, device_id: str, db: AsyncSession):
    # Fetch verified user's chat_id from database
    # Send via telegram_bot_service.send_trade_notification()
```

### 5. Removed All Placeholder Responses

**Before (placeholder):**
```python
async def cmd_portfolio(self, update, context):
    message = (
        "💼 *Portfolio*\n\n"
        f"Total Value: $100,000.00\n"  # HARDCODED!
        f"Positions: 5\n"
    )
```

**After (real data or proper empty state):**
```python
async def cmd_portfolio(self, update, context):
    try:
        response = await client.get("http://localhost:8000/api/v1/portfolio/1/holdings")
        if response.status_code == 200:
            data = response.json()
            holdings = data.get('holdings', [])
            
            if not holdings:
                message = "❌ No positions found\n\nYour portfolio is empty."
            else:
                # Calculate real totals from data
                total_value = sum(h.get('market_value', ...) for h in holdings)
                message = f"💼 *Portfolio*\n\nTotal Value: ${total_value:,.2f}\n..."
        elif response.status_code == 404:
            message = "❌ Portfolio not found"
        else:
            message = f"⚠️ Could not fetch portfolio (HTTP {response.status_code})"
    except httpx.ConnectError:
        message = "❌ Backend not reachable"
```

## Implementation Steps

### Step 1: Install Dependencies
```bash
cd backend
pip install python-telegram-bot==21.0 apscheduler==3.10.4
```

### Step 2: Configure Bot Token
Add to `.env` (project root and `backend/.env`):
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

Get token from @BotFather on Telegram:
1. Message @BotFather
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token

### Step 3: Update main.py
**Imports:**
```python
# Remove
from app.services.embedded_openwa import embedded_openwa, get_embedded_openwa

# Add
from app.api.v1 import telegram_settings, telegram_webhook, telegram_chat
```

**Lifespan (startup):**
```python
if settings.TELEGRAM_BOT_TOKEN:
    from app.services.telegram_bot_service import get_telegram_bot_service
    bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
    await bot_service.initialize()
    asyncio.create_task(bot_service.start_polling())
    logger.info(f"Telegram Bot started - @{bot_service.bot.username}")
```

**Routes:**
```python
app.include_router(telegram_settings.router, prefix="/api/v1", tags=["telegram-settings"])
app.include_router(telegram_webhook.router, tags=["telegram-webhook"])
app.include_router(telegram_chat.router, tags=["telegram-chat"])
# Old WhatsApp routes commented out:
# app.include_router(chat.router, prefix="/api/v1", tags=["whatsapp"])
```

### Step 4: Remove Placeholders from Bot Commands

Every command must:
1. **Fetch real data** from backend API
2. **Return empty state** with helpful message if no data
3. **Return error state** with HTTP code if API fails
4. **Handle connection errors** gracefully

**Pattern:**
```python
async def cmd_example(self, update: Update, context):
    chat_id = update.effective_chat.id
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/api/v1/endpoint")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    message = "❌ No items found\n\nHelpful guidance..."
                else:
                    # Process real data
                    message = format_data(items)
            elif response.status_code == 404:
                message = "❌ Not found\n\nSetup instructions..."
            else:
                message = f"⚠️ Error (HTTP {response.status_code})\n\nTry again..."
                
    except httpx.ConnectError:
        message = "❌ Backend not reachable\n\nMake sure server is running..."
    except Exception as e:
        logger.error(f"Error: {e}")
        message = f"⚠️ Error\n\nDetails: {str(e)[:100]}"
    
    await update.message.reply_text(message, parse_mode="Markdown")
```

### Step 5: Update Frontend Settings
**File:** `frontend/components/SettingsTab.tsx`

**Fix duplicate state:**
```typescript
// REMOVE duplicate declaration
// const [telegram, setTelegram] = useState<TelegramSettings>({...})

// Keep only one with all fields
const [telegram, setTelegram] = useState<TelegramSettings>({
  bot_token: '',
  chat_id: '',
  enabled: true,
  configured: false,
  chat_enabled: true,
  is_verified: false,
  trade_notifications_enabled: true,
  daily_summary_enabled: true,
  summary_time_wat: '20:00',
  ai_explanations_enabled: true,
});
```

**Fix duplicate functions:**
```typescript
// REMOVE duplicate saveTelegram function
// Keep only one that calls correct API endpoint

const saveTelegram = async () => {
  try {
    const deviceId = localStorage.getItem('device_id');
    await fetch(`${API_URL}/api/v1/settings/telegram/configure`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json', 
        'X-Device-ID': deviceId! 
      },
      body: JSON.stringify({
        chat_id: telegram.chat_id,
        bot_token: telegram.bot_token,
        enabled: telegram.enabled,
        chat_enabled: telegram.chat_enabled,
      }),
    });
    setTelegram({ ...telegram, configured: true });
    triggerToast('success', 'Telegram Configured', 'Telegram notifications enabled.');
  } catch (error) {
    triggerToast('error', 'Failed', 'Could not configure Telegram.');
  }
};
```

## Testing Checklist

### Backend
- [ ] Server starts without errors
- [ ] Telegram Bot initializes (check logs for "Bot initialized: @username")
- [ ] `/api/v1/health` returns healthy
- [ ] `/api/v1/settings/telegram/status` returns config state
- [ ] Test message sends via `python test_bot_quick.py`

### Frontend
- [ ] Build succeeds (`npm run build`)
- [ ] No duplicate state declarations
- [ ] No duplicate functions
- [ ] Settings tab renders without errors

### Bot Commands
- [ ] `/start` - Welcome message with bot capabilities
- [ ] `/help` - Command list with examples
- [ ] `/verify` - Returns chat ID with setup instructions
- [ ] `/status` - Returns real config or "not configured"
- [ ] `/portfolio` - Returns real holdings or "empty portfolio"
- [ ] `/trades` - Returns real trades or "no trades yet"
- [ ] `/settings` - Returns preferences or "not configured"
- [ ] Natural chat - Returns AI response or error with guidance

### Error Handling
- [ ] Backend offline → "Backend not reachable" message
- [ ] No data → "No items found" with helpful guidance
- [ ] 404 errors → "Not found" with setup instructions
- [ ] 500 errors → "Service unavailable" message
- [ ] Empty messages → Prompt user to type something

## Why This Matters

Before this implementation:
- ❌ Bot returned hardcoded placeholder data
- ❌ No real integration with backend
- ❌ Users couldn't trust bot responses
- ❌ WhatsApp dependency (complex, requires browser/QR)

After:
- ✅ Bot returns real data from backend
- ✅ Proper empty states guide users
- ✅ Error messages are actionable
- ✅ Telegram is simpler (no QR codes, just bot token)
- ✅ Full 2-way chat with AI
- ✅ Production-ready with webhook support

## Files Modified

1. `backend/app/services/telegram_bot_service.py` - Created
2. `backend/app/api/v1/telegram_settings.py` - Already existed, kept
3. `backend/app/api/v1/telegram_chat.py` - Created
4. `backend/app/api/v1/telegram_webhook.py` - Created
5. `backend/app/main.py` - Updated imports, startup, routes
6. `backend/app/api/v1/trading.py` - Replaced WhatsApp with Telegram notifications
7. `backend/requirements.txt` - Added python-telegram-bot, apscheduler
8. `backend/.env` - Added TELEGRAM_BOT_TOKEN
9. `frontend/components/SettingsTab.tsx` - Removed duplicates
10. `.env.example` - Added Telegram section
11. `backend/.env.render` - Added Telegram for Render deployment

## Botfather Configuration

**Description (set via `/setdescription`):**
```
Jasper Trades AI - Your intelligent trading assistant for the Jasper Trades platform.

📊 What I can do:
• Track your portfolio in real-time
• Notify you of trade executions and closures
• Send daily trading summaries at 8 PM WAT
• Answer questions about your trades and positions
• Provide AI-powered market analysis and signals
• Alert you to system status and risk events

💬 Chat naturally - ask about your portfolio, recent trades, or market conditions.

⚙️ Commands:
/start - Begin using the bot
/help - See all commands
/portfolio - View holdings
/trades - Recent trades
/status - Account status
/settings - Notification prefs
/verify - Get chat ID for setup

Built for swing traders and position traders using the Jasper Trades AI platform.
```

**Commands (set via `/setcommands`):**
```
start - Start the bot and see welcome message
help - Show all available commands and usage examples
status - Check your account status and verification state
portfolio - View current portfolio holdings and PnL
trades - Show recent trade history with details
settings - View Telegram notification preferences
verify - Get your chat ID for app verification
```