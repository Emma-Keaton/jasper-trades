# Jasper Trades - Complete Deployment Guide

## Quick Start (Local Testing)

```bash
# Start both backend and frontend
start.bat
```

This opens two windows:
- **Backend**: http://localhost:8000 (API docs at /docs)
- **Frontend**: http://localhost:3000 (trading dashboard)

**Note:** Database migrations run automatically on startup - no manual setup required!

---

## Part 1: Local Development Setup

### Prerequisites

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Git** (optional)

### Installation

```bash
# Backend
cd backend
pip install -r requirements.txt
copy .env.example .env

# Frontend
cd ..\frontend
npm install
copy .env.example .env.local
```

### Configure API Keys

**Backend (`backend/.env`):**
```env
# LLM configuration
# Gemini 2.5 Flash is the PRIMARY LLM. Set ~3 keys (comma-separated, ideally from
# separate Google accounts) so a rate-limited project never stalls a trade.
GEMINI_API_KEY=key1,key2,key3
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# NVIDIA NIM is the AUTOMATIC FALLBACK when Gemini is down/unconfigured.
# The proxy pings Gemini first and falls back to NVIDIA on failure.
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
# (NVIDIA's per-task model is fixed in backend/app/nvidia_nim.py, e.g.
#  analysis -> meta/llama-3.1-8b-instruct, portfolio -> nvidia/llama-3.3-nemotron-super-49b-v1)

# Gemini model tiers (only used when Gemini is the provider)
MODEL_FAST=gemini-2.5-flash-lite
MODEL_SMART=gemini-2.5-flash
MODEL_DEEP=gemini-2.5-pro

# Telegram Signal Sources (Telethon) - REQUIRED for signal import
# Get API ID + hash from https://my.telegram.org (API development tools)
TELEGRAM_API_ID=1234567
TELEGRAM_API_HASH=your-api-hash
TELEGRAM_SESSION_NAME=jasper

# Public base URL of THIS backend - used by the Telegram bot for callbacks/webhooks.
BACKEND_INTERNAL_URL=https://<your-backend>.onrender.com

# Crypto market data (CCXT multi-CEX, geo-probe gated)
CCXT_EXCHANGES=bybit,okx,kucoin,gate,htx,bingx,bitget,mexc,kraken,coinbase,bitfinex,bitstamp

# Nigerian bank payouts (Optional - or configure via Settings page)
PAYSTACK_SECRET_KEY=
FLUTTERWAVE_SECRET_KEY=

# WalletConnect project ID (EVM wallet connection). Create at https://cloud.walletconnect.com
# Served to the frontend via GET /api/v1/settings/public; not baked into the frontend build.
WALLETCONNECT_PROJECT_ID=your-project-id


# Security (change in production)
SECRET_KEY=change-this-to-random-secret-key
API_AUTH_KEY=change-this-auth-key
CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Run Locally

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

---

## Part 1.5: Automatic Database Setup

**No manual database setup required!** Jasper Trades includes automatic database migration that runs on every application startup.

### What Happens on Startup

1. **Check Tables:** System checks if database tables exist
2. **Create Missing:** Any missing tables are created
3. **Add Columns:** Missing columns are added to existing tables
4. **Preserve Data:** Your existing data is preserved

### Deployment Guarantees

✅ **Local:** First run creates fresh database  
✅ **Render/Cloud:** Database schema auto-updates on deploy  
✅ **Docker:** Migrations run on container start  
✅ **Safe:** Migration is idempotent (safe to run multiple times)

### Troubleshooting Database Errors

If you see database errors like `"no such column"`:

```bash
# 1. Stop the backend
# 2. Delete the database (local only, not production!)
rm backend/data/sqlite/jasper_trades.db

# 3. Restart backend - fresh database created automatically
python -m uvicorn app.main:app --reload
```

**Production:** Database migrations run automatically - no action needed.

See `DATABASE_SETUP.md` for complete migration details.

---

## Part 2: Cloud Deployment (Free)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ FREE CLOUD DEPLOYMENT                                   │
├─────────────────────────────────────────────────────────┤
│ Frontend (Vercel)    - https://jasper-trades.vercel.app│
│ Backend (Render)     - https://jasper-backend.onrender │
│ Telegram Bot (Bot API) - Runs inside backend            │
│ Google Gemini 2.5 Flash - Free tier (multi-key rotation) │
│ Kronos (Render service)  - Price forecaster (separate)   │
└─────────────────────────────────────────────────────────┘

Monthly Cost: $0
```

### Step 1: Push to GitHub

```bash
cd E:\Projects\jasper-trades
git init
git add .
git commit -m "Initial commit"

# Create repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/jasper-trades.git
git branch -M main
git push -u origin main
```

**Important - Add to `.gitignore`:**
```
node_modules/
__pycache__/
*.pyc
backend/data/
backend/.env
frontend/.env.local
```

---

### Step 2: Deploy Backend to Render (Free)

**Render Free Tier:** 500 hours/month, 512MB RAM

1. **Create Account:** https://render.com/ (sign in with GitHub)

2. **Create Web Service:**
   - Click "New +" → "Web Service"
   - Connect repository: Select "jasper-trades"
   - Root Directory: `backend`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11.0
   PORT=10000
   SECRET_KEY=<generate random 32+ chars>
   API_AUTH_KEY=<generate random string>
   CORS_ORIGINS=https://jasper-trades.vercel.app
   WALLETCONNECT_PROJECT_ID=<your-walletconnect-project-id>  # optional; enables WalletConnect QR in Settings
   ```

   **Database — use Supabase for persistence (recommended).** Render free tier wipes its disk on every redeploy, so SQLite data is lost. Supabase Postgres survives redeploys and the app's schema is auto-created on startup (no manual DDL):
   ```
   DATABASE_URL=postgresql://postgres.<ref>:<db_password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
   - Create a project at https://supabase.com → Project Settings → Database → Connection string → **Transaction** pooler (port 6543).
   - Paste it as `DATABASE_URL` (URL-encode any special characters in the password).
   - Optional (only if you use realtime/auth/storage): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
   - The backend detects Postgres from the `postgresql://` scheme and uses the asyncpg driver; migrations run at startup.
   - If you skip Supabase, use `DATABASE_URL=sqlite+aiosqlite:///./data/sqlite/jasper_trades.db` and `DATA_DIR=./data` (data wiped on redeploy).

   **Note:** Leave API keys blank - configure via Settings page after deployment.

4. **Deploy** - Click "Create Web Service"

5. **Keep Alive (Prevent Sleep):**
   Render free tier sleeps after 15 min inactivity. Use UptimeRobot:
   - Go to https://uptimerobot.com/
   - Create free account
   - Add monitor: `https://YOUR_BACKEND.onrender.com/api/v1/health`
   - Check interval: 5 minutes

---

### Step 3: Deploy Frontend to Vercel (Free)

**Vercel Free Tier:** Unlimited deployments, 100GB bandwidth/month

1. **Create Account:** https://vercel.com/ (sign in with GitHub)

2. **Import Project:**
   - Click "Add New Project"
   - Select "jasper-trades" repository
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

3. **Environment Variables:**
   ```
   NODE_ENV=production
   NEXT_PUBLIC_API_URL=https://jasper-backend.onrender.com
   NEXT_PUBLIC_WS_URL=wss://jasper-backend.onrender.com
   ```

4. **Deploy** - Click "Deploy" (2-5 minutes)

**Frontend URL:** `https://jasper-trades.vercel.app`

---

### Step 4: Configure via Settings Page

1. **Open Settings:** `https://jasper-trades.vercel.app/settings`

2. **Configure AI:**
   - **Gemini (primary):** set `GEMINI_API_KEY` in your Render dashboard variables (~3 keys comma-separated, one per Google account). The Settings page reports "Gemini ready" when configured. `GEMINI_API_KEYS` is still read as a deprecated fallback.
   - **NVIDIA NIM (fallback):** Get API key https://build.nvidia.com/, add as `NVIDIA_API_KEY` in the dashboard. On the advanced settings page, paste into "NVIDIA NIM API" → "Test" → "Save All Settings". NVIDIA is used automatically only if Gemini is down/unset.
   - The LLM proxy tries Gemini first and falls back to NVIDIA per task (fast tasks → `nemotron-mini-4b`, analysis → `llama-3.1-8b`, portfolio → `nemotron-super-49b-v1`).

3. **Configure Paper Trading (default, recommended for testing):**
   - Settings → Paper Trading → enable Practice mode
   - The Universal Paper Trading engine handles all assets risk-free
   - Switch to live only when you are comfortable (cTrader/CCXT/Trove/Tiger)

4. **Configure Notifications (Optional):**
   - **Telegram** - Bot token + chat ID (primary; two-way chat + trade alerts)
   - **Discord** - Paste webhook URL
   - **Email** - SendGrid configuration
   - **Slack** - Paste webhook URL

---

## Part 3: Multi-Broker Setup

### Broker Routing

Jasper auto-routes trades by asset class:

| Asset Class | Broker |
|-------------|--------|
| Stocks/Equities (US + Nigerian NGX) | Trove Finance |
| Crypto | Binance |
| Solana Tokens | Solana |

### Configure Multiple Brokers

1. **Trove Finance (Stocks):**
   - Get API key: https://sandbox.api.trovefinance.com/
   - Settings → Trove API
   - Enter API key, enable sandbox mode for testing
   - Save & Test

2. **Binance (Crypto):**
   - Settings → Binance
   - Enter API keys
   - Save

**Result:** When you execute a trade:
- `AAPL`, `TSLA`, `DANGCEM.LAGOS` → Routes to Trove (US + Nigerian stocks)
- `BTCUSDT` → Routes to Binance
- `SOL` → Routes to Solana broker

---

## Part 3.25: Kronos Predictions (Optional)

Kronos is a time-series forecasting model that predicts price movements. It is
deployed as a **separate Render service** (`kronos-service`) — **no Colab is used**.
To enable it, deploy `backend/kronos-service` to Render and set `KRONOS_SERVICE_URL`
to its URL in the main backend. See `backend/kronos-service/README.md`.

**Replacement fallback:** when `KRONOS_SERVICE_URL` is blank (or the service is
unreachable), the backend falls back to a built-in tiered forecaster
(`app/services/forecasting/`, ported from aegis-quant): statsmodels Holt-Winters
when available, otherwise a dependency-free deterministic trend forecaster
(`numpy`). It fetches daily closes via Yahoo chart (keyless, `data_connectors`)
and returns a real `UP`/`DOWN` prediction with confidence — so signal confidence
scoring keeps a Kronos-style basis even without the separate service deployed.

| Feature | Local (4GB RAM) | Separate Render service |
|---------|-----------------|-------------------------|
| **Models** | Kronos-mini only | Kronos (full) |
| **Strategies** | Single model | Cascade, Ensemble, Context |
| **Speed** | ~500-1000ms | ~100-300ms (GPU) |
| **Memory** | ~500MB RAM | ~1GB VRAM (GPU) |
| **Context** | 512 tokens | Up to 2048 tokens |
| **Accuracy** | Good | Better (ensemble) |

### Configure Backend

**Option A: Via `.env` file (quick)**

Edit `backend/.env`:

```env
# Kronos Service
KRONOS_SERVICE_URL="https://your-kronos.onrender.com"
KRONOS_STRATEGY="cascade"
```

**Option B: Via Settings page (recommended)**

1. Go to http://localhost:3000/settings
2. Find "Kronos AI Settings"
3. Enter the Kronos service URL
4. Select strategy:
   - **Cascade** - Fast screening (default, best for 100s of pairs)
   - **Ensemble** - Maximum accuracy (best for final trades)
   - **Context** - Auto-select model by data length
5. Click "Save" and "Test Connection"

### Prediction Strategies

Configure `KRONOS_STRATEGY` based on your use case:

| Strategy | Description | Best For | Speed |
|----------|-------------|----------|-------|
| `cascade` | Filters: mini → small → base | Screening 100s of pairs | ⚡⚡⚡ |
| `ensemble` | Weighted average (20/30/50) | Final trade decisions | ⚡ |
| `context` | Auto-select by data length | Mixed timeframes | ⚡⚡⚡ |
| `mini` | Mini model only | Fastest inference | ⚡⚡⚡ |
| `small` | Small model only | Balanced | ⚡⚡ |
| `base` | Base model only | Highest accuracy | ⚡ |

**Recommended:**
- Day trading/screening: `cascade`
- Swing trading: `ensemble`
- Long-term analysis: `context`

### API Endpoints

Once configured, use these endpoints:

```bash
# Health check
curl {KRONOS_URL}/health

# Single prediction (default strategy)
curl {KRONOS_URL}/predict/AAPL

# Specific strategy
curl "{KRONOS_URL}/predict/AAPL?strategy=ensemble"

# Batch predictions
curl -X POST {KRONOS_URL}/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "NVDA"], "strategy": "cascade"}'

# List all strategies
curl {KRONOS_URL}/strategies
```

### Troubleshooting

**"Kronos: 400" Error:**
- Check the Kronos service is running
- Verify the service URL is current
- Restart the Kronos service if needed

**Timeout Errors:**
- Service may be busy
- Increase timeout to 60 seconds (already configured)
- Try smaller batch size

**Memory Errors:**
- Reduce batch size to 1-2 symbols
- Use `cascade` strategy (filters early)
- Restart the Kronos service

---

## Part 3.3: Auto-Payout Configuration (Flexible Profit Distribution)

### Overview

Production-ready auto-payout system with flexible destination routing:

**Payout Destinations:**
1. **Crypto Wallet** - USDT transfers via Tatum (ERC20/SOLANA/BSC)

**Features:**
- Configurable payout percentage (0-100%)
- Scheduled execution (hourly, daily at specific time)
- Minimum threshold (prevent micro-transactions)
- Real blockchain transfers (no simulated data)
- Full audit trail in database

### Configuration Fields

```json
{
  "payout_enabled": true,
  "payout_percentage": 50.0,
  "payout_schedule_hour": 20,
  "payout_destination": "crypto_wallet",
  "crypto_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595f4bE83",
  "crypto_chain": "ethereum",
  "split_ratio": 50,
  "min_payout_threshold": 10.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `payout_enabled` | boolean | Enable/disable auto-payout |
| `payout_percentage` | number (0-100) | % of daily profit to distribute |
| `payout_schedule_hour` | number (0-23) | Hour in ET timezone for execution |
| `payout_destination` | string | `crypto_wallet` |
| `crypto_wallet` | string | USDT wallet address (ERC20: 0x..., SOLANA: base58) |
| `crypto_chain` | string | `ethereum`, `solana`, or `bsc` |
| `min_payout_threshold` | number | Minimum profit before payout triggers |

### Prerequisites

**Crypto Wallet Payout:**
- Tatum API key (free tier: https://tatumi.com)
- USDT wallet address (ERC20, SOLANA, or BSC)

### Step 1: Configure Tatum API Key (For Crypto Payouts)

1. Go to https://tatumi.com and create account
2. Generate API key (ETH/SOL/BSC mainnet support)
3. In Jasper Trades Settings page:
   - Navigate to "Auto-Payout" tab
   - Enter Tatum API key in dedicated field (or via backend)

**Backend `.env` alternative:**
```env
# Tatum API key for USDT transfers
TATUM_API_KEY=tat_xxxxx
```

### Step 2: Set Payout Configuration

1. Go to Settings → "Auto-Payout"

2. **Enable Auto-Payout:**
   - Toggle "Enable Auto-Payout" ON

3. **Set Percentage:**
   - Adjust slider or enter value (e.g., 50%)
   - This % of daily profit will be distributed

4. **Select Destination:**
   - **Crypto Wallet** - Enter USDT address, select chain (ERC20/SOLANA/BSC)

5. **Set Schedule:**
   - Select hour in ET timezone (e.g., 8 PM ET)
   - Payout executes once daily at this time

6. **Set Minimum Threshold:**
   - Enter minimum profit before payout triggers (e.g., $10)
   - Prevents micro-transactions on small profits

7. **Click "Save Configuration"**

8. **Test (Optional):**
   - Click "Test Payout" button
   - System will execute payout if profit available
   - Check transaction status in notification

### How It Works - Payout Flow

```
Daily Profit Calculation (at scheduled hour)
  ↓
Check: Profit > $0? → No → Skip (no payout)
  ↓
Check: Profit > Threshold? → No → Skip (wait for next day)
  ↓
Calculate: Payout Amount = Profit × (Percentage / 100)
  ↓
Route to destination:
  └─ crypto_wallet → Tatum API → USDT transfer → Your wallet
  ↓
Database audit trail (Withdrawal table)
  ↓
Notification (Telegram/Discord/Email configured)
```

### Real Implementation Details

**Crypto Wallet (Tatum):**
- Direct USDT transfer on blockchain
- Supports: Ethereum (ERC20), Solana (SPL), BSC (BEP20)
- Transaction hash stored in database
- Network fees paid from payout amount
- Real API call: `POST https://api.tatum.io/v3/blockchain/transaction`

### API Endpoints

```bash
# Get payout configuration
GET /api/v1/settings/payout
Headers: X-Device-ID: {device_id}

Response:
{
  "configured": true,
  "payout_config": {
    "payout_enabled": true,
    "payout_percentage": 50.0,
    ...
  }
}

# Save configuration
POST /api/v1/settings/payout
Headers: X-Device-ID: {device_id}
Body: { "payout_config": {...} }

# Test payout (immediate execution)
POST /api/v1/settings/payout/test
Headers: X-Device-ID: {device_id}
Body: { "portfolio_id": 1 }

Response:
{
  "executed": true,
  "status": "completed",
  "amount": 25.50,
  "destination": "crypto_wallet",
  "tx_hash": "0xabc123..."
}
```

### Troubleshooting

**"Insufficient balance" error:**
- Portfolio cash < payout amount
- Ensure trading profits have been realized (trades filled)

**"Tatum API not configured":**
- Add TATUM_API_KEY to settings
- Key must have ETH/SOL mainnet permissions

**"Already paid out today":**
- System prevents duplicate daily payouts
- Wait until next scheduled execution

**"No profit available":**
- Daily PnL must be positive for payout
- Check trading activity in portfolio

### Monitoring & Audit

**View Payout History:**
```bash
GET /api/v1/withdrawals?portfolio_id={id}&type=auto_payout
```

**Database Tables:**
- `withdrawals` - All payout records with status, amounts, tx hashes
- `device_settings` - Encrypted payout configuration

**Notifications:**
- Configured channels (Telegram/Discord/Email) receive:
  - Payout executed notification
  - Transaction hash
  - Amount and destination details

### Production Checklist

- [ ] Tatum API key configured and tested
- [ ] Crypto wallet address validated (test transaction sent)
- [ ] Payout percentage set (0-100%)
- [ ] Schedule hour configured (ET timezone)
- [ ] Minimum threshold set ($10 recommended)
- [ ] Test payout executed successfully
- [ ] Notifications configured for payout alerts
- [ ] Database backups enabled (Withdrawal table audit trail)

### Cost Estimates

**Tatum API:**
- Free tier: 100 transactions/month
- Paid: $99/month for 1000 transactions
- Gas fees: Additional (paid in ETH/SOL/BNB)

---

## Part 3.5: Free Market Data & Notifications

### Market Data Providers (Settings → Market Data)

Configure free market data APIs for real-time prices, news, and sentiment analysis.

#### CoinGecko (Crypto Prices) - ✅ ALWAYS ACTIVE
- **FREE** - No API key required!
- Real-time crypto prices (Bitcoin, Ethereum, 1000+ altcoins)
- Market caps, volume, 24h changes
- Top gainers/losers
- Trending coins

**No setup needed** - Works immediately!

#### Alpha Vantage (Stocks/Forex/Sentiment)
- **FREE Tier:** 5 calls/min, 500 calls/day
- **Get API Key:** https://www.alphavantage.co/support/#api-key

**Setup:**
1. Go to Alpha Vantage API Key page
2. Enter email (no credit card)
3. Copy API key (instant)
4. Settings → Market Data → Alpha Vantage → Paste key
5. Click "Test" → "Save"

**What you get:**
- Real-time US stock prices
- Forex exchange rates (150+ currencies)
- News sentiment analysis (bullish/bearish)
- Technical indicators (RSI, MACD, etc.)

#### Finnhub (Real-Time Stocks)
- **FREE Tier:** 60 calls/min
- **Get API Key:** https://finnhub.io/dashboard

**Setup:**
1. Sign up free (no credit card)
2. Copy API key from dashboard
3. Settings → Market Data → Finnhub → Paste key
4. Test & Save

**What you get:**
- Real-time US stock quotes (NYSE, NASDAQ)
- Company news feed
- SEC filings (10-K, 10-Q, 8-K)
- Insider transactions
- Social sentiment (Reddit, Twitter)

#### Twelve Data (Stocks/Forex/Crypto)
- **FREE Tier:** 800 calls/day, 8 calls/min
- **Get API Key:** https://twelvedata.com/pricing

**Setup:**
1. Click "Start Free" (no credit card)
2. API key in dashboard
3. Settings → Market Data → Twelve Data → Paste key

#### FRED (Economic Data) - OPTIONAL
- **FREE** - Federal Reserve Economic Data
- **Get API Key:** https://fred.stlouisfed.org/docs/api/api_key.html
- US Treasury yields, GDP, inflation rates

---

### Email Notifications (SendGrid)

**FREE:** 100 emails/day forever

**Get Started:**
1. Go to https://signup.sendgrid.com/
2. Create free account (no credit card)
3. Verify email
4. Settings → API Keys → Create API Key
   - Name: "Jasper Trades"
   - Permissions: Full Access
   - Copy key (starts with "SG.")
5. In Jasper: Settings → Email (SendGrid)
   - Paste API key
   - Enter "From Email"
   - Enable & Save
6. Send test email to verify

**Email Templates Included:**
- 📈 Trade execution confirmations
- 🔔 Price alert notifications
- 📊 Daily P&L summary (every morning)
- 📈 Weekly performance report
- ⚠️ System alerts

**Important:** Verify your "From Email" in SendGrid's Sender Authentication settings, or emails may not be delivered.

---

### Discord Bot (Two-Way Chat)

**FREE** - Unlimited messages, no rate limits

Unlike webhooks (send-only), the Discord bot enables two-way communication:
- Type commands like `!portfolio`, `!trades`, `!help`
- Get instant responses
- Ask AI trading questions

**Complete Setup:**

**Step 1: Create Discord Application**
1. Go to https://discord.com/developers/applications
2. "New Application" → Name it "Jasper Trades" → Create
3. "Bot" → "Add Bot" → "Yes, do it!"

**Step 2: Get Bot Token**
1. In Bot settings → "Reset Bot Token"
2. **IMPORTANT:** Copy token immediately (only shown once!)
3. Settings → Discord Bot → Paste "Bot Token"

**Step 3: Add Bot to Server**
1. "OAuth2" → "URL Generator"
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions:
   - Send Messages
   - Read Message History
   - Embed Links
   - Attach Files
4. Copy generated URL
5. Paste in browser → Select server → Authorize

**Step 4: Get Server & Channel IDs**
1. Discord Settings → Advanced → Enable "Developer Mode"
2. **Server ID:** Right-click server icon → "Copy ID"
3. **Channel ID:** Right-click channel → "Copy ID"
4. Paste both in Settings → Discord Bot

**Step 5: Start Bot**
1. Enable "Discord bot" checkbox
2. Click "Start Bot"
3. Wait for "Bot Connected" (green)
4. In Discord, type `!help` to test

**Available Commands:**
- `!portfolio` - Portfolio summary
- `!trades` - Recent trades today
- `!help` - List all commands
- `!status` - Bot status
- Plus AI chat: "Should I buy AAPL?"

---

## Part 4: Trading Caps & Risk Management

### What are Trading Caps?

Trading caps protect your portfolio by limiting:
- **Max Position Amount** - Maximum $ per trade (e.g., $5,000)
- **Max Position %** - Maximum % of portfolio per trade (e.g., 20%)
- **Daily Loss Limit** - Stop trading after $X loss (e.g., $2,000)
- **Daily Loss %** - Stop trading after X% portfolio loss (e.g., 5%)

### Configure Trading Caps

1. **Go to Settings → Trading Caps & Risk Limits**

2. **Set Limits:**
   ```
   Max Position Amount: $5,000
   Max Position %: 20%
   Daily Loss Limit: $2,000
   Daily Loss %: 5%
   ```

3. **Choose Enforcement:**
   - **Hard Limit** (Recommended) - Block any trade exceeding caps
   - **Soft Limit** - Warn but allow (for testing)

4. **Enable & Save**

### Recommended Settings

| Account Size | Max Position | Max % | Daily Loss |
|--------------|--------------|-------|------------|
| $1,000 | $200 | 20% | $50 (5%) |
| $10,000 | $2,000 | 20% | $500 (5%) |
| $100,000 | $20,000 | 20% | $5,000 (5%) |

### How It Works

When a trade is executed:
1. System checks proposed position against caps
2. If exceeds hard limit → Trade blocked
3. If exceeds soft limit → Warning shown, trade allowed
4. Daily loss tracked in real-time
5. Once daily limit hit → Trading suspended until reset (midnight ET)

---

## Part 5: Paper vs Live Trading

### Switch Modes

**Via Settings Page (Recommended):**
1. Go to Settings
2. Find " Trading" section
3. Toggle "Paper Trading Mode"
4. Save

**Via Environment Variable:**
```env
# Paper Trading (Default)

# Live Trading
_PAPER=false
```

### Verification

```bash
curl https://YOUR_BACKEND.onrender.com/api/v1/status
```

Response shows:
```json
{
  "broker_status": {
    "": {
      "connected": true,
      "paper_trading": true  // Current mode
    }
  }
}
```

---

## Cost Breakdown

| Service | Free Tier | What You Get | Cost |
|---------|-----------|--------------|------|
| **Vercel** | Hobby | Unlimited deployments, 100GB/mo | $0 |
| **Render** | Free | 500 hours/month, 512MB RAM | $0* |
| **NVIDIA NIM** | Free tier | $25 credits/month | $0 (testing) |
| **Tatum** | Free tier | 100 transactions/month | $0 |
| **UptimeRobot** | Free | 50 monitors | $0 |
| **Total** | | | **$0/month** |

*With UptimeRobot keeping it awake 24/7

### Scaling Path (Paid)

| Upgrade | Cost | Benefit |
|---------|------|---------|
| **Render Standard** | $7/mo | Always-on, no cold starts |
| **Railway** | $5/mo | 2GB RAM, no sleep |
| **NVIDIA Paid** | $0.15-3/1M tokens | Higher rate limits |

---

## Troubleshooting

### Backend Sleeps Despite UptimeRobot
- Check monitor is active: https://uptimerobot.com/dashboard
- Verify URL: `https://YOUR_BACKEND.onrender.com/api/v1/health`
- Ensure 5-minute interval (not 10)

### Telegram Not Working
1. Verify the bot token is configured in Settings → Telegram
2. Check backend logs for Telegram webhook startup
3. Test: `curl https://YOUR_BACKEND.onrender.com/api/v1/settings/telegram/test`

### Frontend Shows "Disconnected"
1. Check backend URL in Vercel environment variables
2. Verify Render deployment succeeded
3. Check CORS includes Vercel URL:
   ```
   CORS_ORIGINS=https://jasper-trades.vercel.app
   ```

### Settings Not Saving
1. Verify database exists on Render
2. Check encryption key generated
3. Verify X-Device-ID header in requests

### Trading Caps Not Blocking Trades
Backend optimized for 4GB RAM:
- Check Kronos settings
- Reduce batch size if needed
- Use `kronos-mini-int8` model

---

## Security Checklist

- [ ] SECRET_KEY changed from default (32+ random chars)
- [ ] API_AUTH_KEY generated randomly
- [ ] CORS_ORIGINS set to production domain
- [ ] Paper trading enabled for testing
- [ ] Database backups configured (optional)

**Generate Secure Keys:**
```bash
# Windows (PowerShell)
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# Linux/Mac
openssl rand -hex 32
```

---

## Monitoring & Alerts

### Uptime Monitoring
- **UptimeRobot:** Free 50 monitors
- Monitor: `https://YOUR_BACKEND.onrender.com/api/v1/health`
- Alerts: Email, SMS (free)

### Error Tracking
- **Sentry:** Free 5K errors/month
- Add to backend: `pip install sentry-sdk`

### Logs
- **Render:** Dashboard → Logs
- **Vercel:** Project → Deployments → View logs

---

## Backup Strategy

### Database (Render)
Manual backup (Render free tier has no auto-backup):
```bash
curl https://YOUR_BACKEND.onrender.com/api/v1/backup > backup.db
```

### Settings (Encrypted)
Settings stored encrypted in database - export monthly via Settings page.

---

## Success Checklist

Your deployment is successful when:
- [✅] Frontend loads from Vercel
- [✅] Backend API responds from Render
- [✅] Telegram notifications work (if configured)
- [✅] NVIDIA API key configured
- [✅] Test trade executed (paper mode)
- [✅] Mobile access works
- [✅] Multi-broker routing functional
- [✅] Trading caps configured (risk management active)

---

## Next Steps

1. **Test thoroughly** with paper trading
2. **Monitor NVIDIA usage** (stay within $25 free tier)
3. **Configure notifications** (Telegram, Discord, etc.)
4. **Set up alerts** (UptimeRobot + Sentry)
5. **Configure trading caps** (protect your portfolio)
6. **Switch to live trading** when ready (uncheck Paper Trading)

---

**🎉 Congratulations! Jasper Trades is deployed!**

For support:
- Render logs: Dashboard → Logs
- Vercel logs: Deployments → View logs
- API docs: `https://YOUR_BACKEND.onrender.com/docs`

**Happy Trading! 📈🚀**