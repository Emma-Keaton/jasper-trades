import pathlib

p = pathlib.Path('E:/Projects/jasper-trades/backend/.env.example')
t = p.read_text(encoding='utf-8')

# Replace GROQ_API_KEY section
old_groq = 'GROQ_API_KEY='
new_groq = '''# ───────────────────────────────────────────────────────────────────────────────
# GROQ_API_KEY (REQUIRED) - Primary LLM Provider
# ───────────────────────────────────────────────────────────────────────────────
# Multiple keys recommended for rotation (comma-separated).
# HOW TO GET GROQ_API_KEY:
# 1. Go to https://console.groq.com/keys
# 2. Sign up / log in (free tier available)
# 3. Click "Create API Key"
# 4. Name it (e.g., "jasper-trades-prod")
# 5. Copy the key (starts with "gsk_")
# 6. Repeat 2-3 times for multiple keys (rotation avoids rate limits)
# 7. Set as comma-separated: GROQ_API_KEY=gsk_xxx,gsk_yyy,gsk_zzz
# Why multiple keys? Groq has per-key rate limits. The app rotates keys automatically.
GROQ_API_KEY='''

# Replace TELEGRAM_BOT_TOKEN section 
old_telegram = 'TELEGRAM_BOT_TOKEN=""'
new_telegram = '''# ───────────────────────────────────────────────────────────────────────────────
# TELEGRAM_BOT_TOKEN (REQUIRED) - Trade Alerts & Two-Way Chat
# ───────────────────────────────────────────────────────────────────────────────
# HOW TO GET TELEGRAM_BOT_TOKEN:
# 1. Open Telegram, search for @BotFather
# 2. Send /newbot
# 3. Choose a name: "Jasper Trades"
# 4. Choose a username ending in "bot": "myjaspertrades_bot"
# 5. Copy the token (format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
# 6. Set TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
# 7. Get your Chat ID: Message your bot, then visit:
#    https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
# 8. Look for "chat":{"id":123456789} — that's your TELEGRAM_CHAT_ID
TELEGRAM_BOT_TOKEN=""'''

# Replace TELEGRAM_WEBHOOK_SECRET section
old_webhook = 'TELEGRAM_WEBHOOK_SECRET=""'
new_webhook = '''# ───────────────────────────────────────────────────────────────────────────────
# TELEGRAM_WEBHOOK_SECRET (Optional) - Webhook verification
# ───────────────────────────────────────────────────────────────────────────────
# Required for webhook request verification when running behind a tunnel.
# Generate a random string: python -c "import secrets; print(secrets.token_urlsafe(32))"
TELEGRAM_WEBHOOK_SECRET=""'''

updated = t.replace(old_groq, new_groq).replace(old_telegram, new_telegram).replace(old_webhook, new_webhook)

if updated != t:
    pathlib.Path('E:/Projects/jasper-trades/backend/.env.example').write_text(updated, encoding='utf-8')
    print('Updated successfully')
else:
    print('No changes made - patterns not found')