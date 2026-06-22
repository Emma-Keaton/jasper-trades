# Telegram Setup Guide for Jasper Trades

## Overview

Jasper Trades now uses Telegram for notifications instead of WhatsApp. This is **simpler, free, and works on Render** without requiring a browser or QR codes.

## Architecture

- **One global bot** - You create a single Telegram bot for your Jasper Trades instance
- **Per-user chat IDs** - Each user enters their Telegram chat ID in settings
- **Personalized notifications** - Bot sends each user only their own trades and summaries

## Step 1: Create Your Telegram Bot (Production)

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the prompts:
   - Choose a name: `Jasper Trades`
   - Choose a username: `jasper_trades_bot` (must end in `bot`)
4. BotFather will give you a **Bot Token** like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
5. **Save this token** - you'll add it to Render

## Step 2: Configure Render Environment Variables

In your Render dashboard, add these environment variables:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_ENABLED=true
```

**Optional**: Set a default chat ID for testing:
```
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## Step 3: How Users Get Their Chat ID

Each user needs to find their Telegram chat ID:

### Method 1: Via BotFather (Easiest)
1. Start a conversation with your bot on Telegram
2. Send `/start` to activate the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for a response like:
```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "chat": {
          "id": 987654321,
          "first_name": "Your Name",
          "type": "private"
        }
      }
    }
  ]
}
```
5. Your chat ID is the `id` field (e.g., `987654321`)

### Method 2: Use a Bot
1. Search for `@userinfobot` on Telegram
2. Start a conversation
3. It will reply with your chat ID

## Step 4: Configure Telegram in Settings Page

1. Go to Jasper Trades Settings → Notifications
2. Find the **Telegram** section
3. Enter:
   - **Chat ID**: Your chat ID from Step 3
   - **Bot Token**: (Optional - only if you want to override the global token)
4. Click **Send Verification Code**
5. Check your Telegram - you'll receive a 6-digit code
6. Enter the code in the settings page
7. Click **Verify**

## Features

Once configured, users receive:

### Trade Executions
```
🔔 TRADE EXECUTED

BUY 10 AAPL
━━━━━━━━━━━━━━━━━━━━
💰 Price: $175.50
💵 Total: $1,755.00
🤖 Agent: AI
📈 Type: MARKET
━━━━━━━━━━━━━━━━━━━━
⏰ 2026-06-19 14:30:00
```

### Trade Closures (with PnL)
```
✅ TRADE CLOSED - WIN

SELL 10 AAPL
━━━━━━━━━━━━━━━━━━━━
💰 Entry: $175.50
💰 Exit: $180.25
📊 PnL: $47.50 (+2.71%)
⏱ Hold: 2h 15m
━━━━━━━━━━━━━━━━━━━━
⏰ 2026-06-19 16:45:00
```

### Daily Summaries
Sent automatically at 8:00 PM WAT (configurable)
```
📊 DAILY SUMMARY

📅 Friday, Jun 19, 2026
━━━━━━━━━━━━━━━━━━━━
💰 Total PnL: +$1,250.00
📈 Return: +2.50%
📊 Win Rate: 75.0%
🎯 Trades: 12
━━━━━━━━━━━━━━━━━━━━
🤖 Jasper Trades AI
```

## Troubleshooting

### "No TELEGRAM_BOT_TOKEN set"
- Check Render environment variables
- Ensure bot token is correctly copied (no extra spaces)
- Restart Render service after adding variables

### "Verification code not received"
- Make sure you started a conversation with the bot
- Send `/start` to activate the bot
- Check if bot token is valid in Render

### "Chat ID not verified"
- Enter the correct chat ID (numeric, no `@` symbol)
- Complete verification within 10 minutes
- Request a new code if expired

### Bot not sending messages
1. Check bot token in Render
2. Verify user's chat ID is correct
3. Ensure user started conversation with bot
4. Check Render logs for errors

## Migration from WhatsApp

If you were using WhatsApp before:

1. **Database**: Run the migration script:
```bash
cd backend
python migrate_whatsapp_to_telegram.py
```

2. **Users**: Each user needs to:
   - Get their Telegram chat ID
   - Re-verify in settings page
   - Old WhatsApp configs will be ignored

3. **Remove old files**:
```bash
# WhatsApp service files already deleted
# Just ensure TELEGRAM_BOT_TOKEN is set in Render
```

## Benefits Over WhatsApp

| Feature | WhatsApp (OpenWA) | Telegram |
|---------|------------------|----------|
| **Cost** | Free | Free |
| **QR Code** | Required (every 30 days) | Not required |
| **Browser** | Required (blocked on Render) | Not required |
| **Setup** | Complex | Simple |
| **Reliability** | Unreliable on free hosting | Works everywhere |
| **Messages** | Limited | Unlimited |
| **Rate Limits** | Strict | Generous |

## Security Notes

- Bot token is stored in Render environment variables (encrypted at rest)
- User chat IDs are stored in database
- Messages sent via HTTPS to Telegram Bot API
- No user credentials stored - bot can only send, not receive personal data

---

**Need help?** Check the backend logs on Render for detailed error messages.