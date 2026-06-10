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

# Install OpenWA for WhatsApp (optional)
npm install @open-wa/wa-automate

# Frontend
cd ..\frontend
npm install
copy .env.example .env.local
```

### Configure API Keys

**Backend (`backend/.env`):**
```env
# NVIDIA NIM API (Required)
NVIDIA_API_KEY=nvapi-your-key-here

# Alpaca (Optional - can configure via Settings page)
ALPACA_API_KEY=PK_xxxxx
ALPACA_API_SECRET=xxxxx
ALPACA_PAPER=true

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

### WhatsApp Setup (Optional)

1. **Install OpenWA:**
   ```bash
   cd backend
   npm install @open-wa/wa-automate
   ```

2. **Start Backend** - OpenWA auto-starts on port 3001

3. **Configure in Settings:**
   - Go to http://localhost:3000/settings
   - Enter phone number
   - Click "Save Config" → "Test"

4. **Chat Commands:**
   - `"portfolio status"` - Get portfolio summary
   - `"what trades today"` - Recent trades
   - `"should I buy AAPL"` - AI analysis
   - `"is market open"` - Market hours
   - `"help"` - List all commands

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
│ WhatsApp (Embedded)  - Runs inside backend              │
│ NVIDIA NIM API       - Free tier ($25 credits/month)   │
│ Google Colab         - Kronos GPU (optional, free)     │
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
   DATABASE_URL=sqlite+aiosqlite:///./data/sqlite/jasper_trades.db
   DATA_DIR=./data
   SECRET_KEY=<generate random 32+ chars>
   API_AUTH_KEY=<generate random string>
   CORS_ORIGINS=https://jasper-trades.vercel.app
   ```
   
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

2. **Configure NVIDIA:**
   - Get API key: https://build.nvidia.com/
   - Paste into "NVIDIA NIM API"
   - Click "Test" → "Save All Settings"

3. **Configure Alpaca:**
   - Sign up: https://alpaca.markets/ (free)
   - Get API keys from dashboard
   - Paste into "Alpaca Trading"
   - Check "Paper Trading Mode"
   - Click "Save"

4. **Configure Notifications (Optional):**
   - **WhatsApp** - Enter phone number, save, test
   - **Discord** - Paste webhook URL
   - **Slack** - Paste webhook URL
   - **Email** - SMTP configuration
   - **Telegram** - Bot token + chat ID

---

## Part 3: Multi-Broker Setup

### Broker Routing

Jasper auto-routes trades by asset class:

| Asset Class | Broker |
|-------------|--------|
| Stocks/Equities | Alpaca |
| Crypto | Binance |
| Solana Tokens | Solana |
| Forex/CFD | Exness (MT5) |
| Futures/Forex | IBKR |

### Configure Multiple Brokers

1. **Alpaca (Stocks):**
   - Settings → Alpaca Trading
   - Enter API keys
   - Save

2. **Binance (Crypto):**
   - Settings → Binance
   - Enter API keys
   - Save

3. **Exness/MT5 (Forex/CFD):**
   - **Requirements:**
     - Windows with MT5 installed (for local hosting)
     - OR Exness API credentials (for cloud hosting)
   - **Setup:**
     - Settings → Exness/MT5 Account
     - Enter MT5 Login ID (e.g., 87291043)
     - Select server (e.g., Exness-MT5-Real6)
     - Enter trading password
     - Click "Link Account"
   - **Local Hosting (Windows):** Trades execute via MT5 terminal
   - **Cloud Hosting (Linux):** Trades use Exness REST API (requires separate API key/secret)

4. **IBKR (Futures/Forex):**
   - Requires IB Gateway running
   - Settings → Brokers → IBKR
   - Enter host, port, client ID
   - Save

**Result:** When you execute a trade:
- `AAPL` → Routes to Alpaca
- `BTCUSDT` → Routes to Binance
- `EURUSD` → Routes to Exness (MT5)
- `SOL` → Routes to Solana broker

---

## Part 3.25: Kronos Colab Setup (Optional - Enhanced AI Predictions)

### What is Kronos Colab?

Kronos is a time-series forecasting model that predicts price movements. The Colab integration gives you:

| Feature | Local (4GB RAM) | Colab GPU (Free Tier) |
|---------|-----------------|----------------------|
| **Models** | Kronos-mini only | 3 models (mini/small/base) |
| **Strategies** | Single model | Cascade, Ensemble, Context |
| **Speed** | ~500-1000ms | ~100-300ms (GPU) |
| **Memory** | ~500MB RAM | ~1GB VRAM (Colab's) |
| **Context** | 512 tokens | Up to 2048 tokens |
| **Accuracy** | Good | Better (ensemble) |

### Step 1: Run Kronos Colab Notebook

1. **Open Google Colab:**
   - Go to https://colab.research.google.com/
   - Click "Upload" → Upload `kronos_colab.ipynb` from your project

2. **Run All Cells in Order:**
   - Cell 1: Install dependencies (2-3 minutes)
   - Cell 2: Load 3 Kronos models (1-2 minutes)
   - Cell 3: Define prediction functions
   - Cell 4: Start API server
   - Cell 5: Get public URL (copy this!)

3. **Keep Colab Running:**
   - Click Runtime → Never idle when asleep
   - Run Cell 6 (auto-connect) to extend session
   - Colab free tier: up to 12 hours/session

### Step 2: Get ngrok Public URL

After running Cell 5, you'll see output like:

```
🌐 Public URL: https://abc123def456.ngrok-free.app

📋 API Endpoints:
  - Health:    https://abc123def456.ngrok-free.app/health
  - Predict:   https://abc123def456.ngrok-free.app/predict/AAPL?strategy=cascade
  - Strategies:{public_url}/strategies
```

**Copy the Public URL** (e.g., `https://abc123def456.ngrok-free.app`)

### Step 3: Configure Backend

**Option A: Via `.env` file (quick)**

Edit `backend/.env`:

```env
# Kronos Colab Integration
KRONOS_COLAB_URL="https://abc123def456.ngrok-free.app"
KRONOS_COLAB_STRATEGY="cascade"
```

**Option B: Via Settings page (recommended)**

1. Go to http://localhost:3000/settings
2. Find "Kronos AI Settings"
3. Enter Colab URL
4. Select strategy:
   - **Cascade** - Fast screening (default, best for 100s of pairs)
   - **Ensemble** - Maximum accuracy (best for final trades)
   - **Context** - Auto-select model by data length
5. Click "Save" and "Test Connection"

### Step 4: Test Integration

```bash
cd backend
python -m app.tests.kronos_test
```

Expected output:
```
✅ LOCAL KRONOS TEST PASSED
✅ COLAB INTEGRATION TEST PASSED
Best strategy: ensemble
```

### Prediction Strategies

Configure `KRONOS_COLAB_STRATEGY` based on your use case:

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
curl {COLAB_URL}/health

# Single prediction (default strategy)
curl {COLAB_URL}/predict/AAPL

# Specific strategy
curl "{COLAB_URL}/predict/AAPL?strategy=ensemble"

# Batch predictions
curl -X POST {COLAB_URL}/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "NVDA"], "strategy": "cascade"}'

# List all strategies
curl {COLAB_URL}/strategies
```

### Troubleshooting

**Colab URL Expired:**
- Colab URLs change each session
- Update `KRONOS_COLAB_URL` in Settings after reconnecting

**"Colab: 400" Error:**
- Check Colab notebook is still running
- Verify ngrok URL is current
- Re-run Cell 4 (restart API server)

**Timeout Errors:**
- Colab GPU may be busy
- Increase timeout to 60 seconds (already configured)
- Try smaller batch size

**Memory Errors on Colab:**
- Reduce batch size to 1-2 symbols
- Use `cascade` strategy (filters early)
- Restart Colab runtime

### Cost

**Google Colab Free Tier:**
- 12 hours per session
- ~15 GB GPU VRAM
- ~12 GB system RAM
- No credit card required

**Note:** Colab may occasionally disconnect during peak hours. For production use, consider:
- Colab Pro ($10/month): Priority access, longer sessions
- Cloud GPU (Lambda Labs, Vast.ai): $0.10-0.50/hour

---

## Part 3.3: Auto-Payout Configuration (Flexible Profit Distribution)

### Overview

Production-ready auto-payout system with flexible destination routing:

**Payout Destinations:**
1. **Crypto Wallet** - USDT transfers via Tatum (ERC20/SOLANA/BSC)
2. **Forex Account** - Reinvest profits into Exness MT5 account
3. **Split Mode** - Distribute between crypto and forex simultaneously

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
| `payout_destination` | string | `crypto_wallet`, `forex_account`, or `split` |
| `crypto_wallet` | string | USDT wallet address (ERC20: 0x..., SOLANA: base58) |
| `crypto_chain` | string | `ethereum`, `solana`, or `bsc` |
| `split_ratio` | number (0-100) | % to crypto (remainder to forex) - only for split mode |
| `min_payout_threshold` | number | Minimum profit before payout triggers |

### Prerequisites

**Option 1: Crypto Wallet Payout**
- Tatum API key (free tier: https://tatumi.com)
- USDT wallet address (ERC20, SOLANA, or BSC)

**Option 2: Forex Reinvestment**
- Exness MT5 account configured in Settings
- MT5 terminal installed (Windows) OR Exness API credentials

**Option 3: Split Mode**
- Both crypto wallet AND Exness MT5 account configured

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

### Step 2: Configure Exness MT5 (For Forex Reinvestment)

1. Navigate to "Exness/MT5 Account" tab in Settings
2. Enter:
   - MT5 Login ID (e.g., `87291043`)
   - Server (e.g., `Exness-MT5-Real6`)
   - Trading password (encrypted storage)
3. Click "Link Account" and "Sync" to verify

### Step 3: Set Payout Configuration

1. Go to Settings → "Auto-Payout"

2. **Enable Auto-Payout:**
   - Toggle "Enable Auto-Payout" ON

3. **Set Percentage:**
   - Adjust slider or enter value (e.g., 50%)
   - This % of daily profit will be distributed

4. **Select Destination:**
   - **Crypto Wallet** - Enter USDT address, select chain (ERC20/SOLANA/BSC)
   - **Forex Account** - Reinvest 100% into MT5 (compounding)
   - **Split** - Set ratio (e.g., 50% crypto, 50% forex reinvestment)

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
Route based on destination:
  ├─ crypto_wallet → Tatum API → USDT transfer → Your wallet
  ├─ forex_account → MT5 internal transfer → Exness balance
  └─ split → Both simultaneously (ratio-based split)
  ↓
Database audit trail (Withdrawal table)
  ↓
Notification (WhatsApp/Discord/Email configured)
```

### Real Implementation Details

**Crypto Wallet (Tatum):**
- Direct USDT transfer on blockchain
- Supports: Ethereum (ERC20), Solana (SPL), BSC (BEP20)
- Transaction hash stored in database
- Network fees paid from payout amount
- Real API call: `POST https://api.tatum.io/v3/blockchain/transaction`

**Forex Reinvestment (MT5):**
- Internal transfer via MetaTrader 5
- Requires MT5 terminal running (Windows)
- Instant settlement, no fees
- Transaction ref: `MT5_{order_number}`
- Falls back to Exness REST API if cloud-hosted

**Split Mode:**
- Two parallel transactions
- Crypto portion: Real Tatum transfer
- Forex portion: MT5 internal transfer
- Both logged separately in audit trail

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

**"MT5 not available":**
- MT5 terminal must be installed and running (Windows)
- Check `MetaTrader5` Python package installed: `pip install MetaTrader5`
- For cloud hosting, use Exness REST API method (requires partner credentials)

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
- Configured channels (WhatsApp/Discord/Email) receive:
  - Payout executed notification
  - Transaction hash
  - Amount and destination details

### Production Checklist

- [ ] Tatum API key configured and tested
- [ ] Crypto wallet address validated (test transaction sent)
- [ ] Exness MT5 account linked (if using forex reinvestment)
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

**MT5 Internal Transfers:**
- Free (no transaction fees)
- Instant settlement

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
2. Find "Alpaca Trading" section
3. Toggle "Paper Trading Mode"
4. Save

**Via Environment Variable:**
```env
# Paper Trading (Default)
ALPACA_PAPER=true

# Live Trading
ALPACA_PAPER=false
```

### Verification

```bash
curl https://YOUR_BACKEND.onrender.com/api/v1/status
```

Response shows:
```json
{
  "broker_status": {
    "alpaca": {
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
| **Alpaca** | Paper trading | Unlimited | $0 |
| **Exness** | Free account | Forex/CFD trading | $0 (Standard spreads) |
| **MT5 Terminal** | Free | Desktop trading platform | $0 |
| **UptimeRobot** | Free | 50 monitors | $0 |
| **Total** | | | **$0/month** |

*With UptimeRobot keeping it awake 24/7

### Exness Trading Costs

| Account Type | Spread EURUSD | Commission | Min Deposit |
|--------------|---------------|------------|-------------|
| Standard | From 1.0 pip | $0 | $10 |
| Raw Spread | From 0.0 pip | $7/lot | $100 |
| Pro | From 0.0 pip | $7/lot | $1,000 |

**Note:** Exness charges via spreads (built into trade price), not platform fees.

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

### WhatsApp Not Working
1. Check OpenWA installed: `backend/node_modules/@open-wa/wa-automate`
2. Verify backend logs for OpenWA startup
3. Re-scan QR code if session expired
4. Test: `curl https://YOUR_BACKEND.onrender.com/whatsapp/status`

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

### Exness/MT5 Connection Issues

**Local Hosting (Windows):**
1. Ensure MT5 terminal is installed and running
2. Verify login credentials in MT5 first (manual login test)
3. Check server name matches exactly (case-sensitive)
4. Restart MT5 terminal if connection stale

**Cloud Hosting (Linux/Render):**
1. MT5 library not available on Linux
2. Must use Exness REST API instead
3. Configure Exness API key/secret in Settings
4. Trades will route via REST API (slower but works on cloud)

### Trading Caps Not Blocking Trades
1. Verify caps are enabled (green "Active" badge)
2. Check enforcement mode (Hard vs Soft limit)
3. Ensure portfolio ID is set (create portfolio first)
4. Review backend logs for cap validation

### Withdrawal to Exness Fails
1. Verify Exness account linked in Settings
2. Check MT5 connection status (should show "Connected")
3. For cloud hosting, configure Exness REST API credentials
4. Withdrawal may require manual processing on Exness side

### High Memory Usage
Backend optimized for 4GB RAM:
- Check Kronos settings
- Reduce batch size if needed
- Use `kronos-mini-int8` model

---

## Local vs Cloud Hosting Comparison

### Local Hosting (Windows)

**Advantages:**
- ✅ Full MT5 terminal integration
- ✅ Fastest execution (direct terminal access)
- ✅ No cloud hosting costs
- ✅ Full control over data

**Requirements:**
- Windows 10/11
- MetaTrader 5 installed
- Python 3.11+
- Node.js 18+

**Setup:**
```bash
# Install MT5 from https://www.exness.com/
# Install Python dependencies
pip install MetaTrader5

# Start backend
python -m uvicorn app.main:app --reload
```

### Cloud Hosting (Linux - Render/Vercel)

**Advantages:**
- ✅ Always online
- ✅ No local machine required
- ✅ Automatic scaling
- ✅ Built-in monitoring

**Limitations:**
- ❌ MT5 library not available (Linux)
- ❌ Must use Exness REST API instead
- ❌ Slightly higher latency

**Workaround:**
- Configure Exness REST API credentials in Settings
- Trades execute via REST API (not MT5 terminal)
- For best of both: Run MT5 locally + cloud frontend

### Hybrid Approach (Recommended)

1. **Backend:** Run locally on Windows machine (MT5 available)
2. **Frontend:** Deploy to Vercel (cloud access)
3. **Expose Backend:** Use ngrok or Cloudflare Tunnel
   ```bash
   # Install ngrok
   ngrok http 8000
   
   # Use ngrok URL in Vercel env vars
   NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
   ```

**Result:** MT5 execution + cloud-accessible frontend

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
- [✅] WhatsApp notifications work (if configured)
- [✅] NVIDIA API key configured
- [✅] Test trade executed (paper mode)
- [✅] Mobile access works
- [✅] Multi-broker routing functional
- [✅] Exness account linked (if using Forex/CFD)
- [✅] Trading caps configured (risk management active)
- [✅] MT5 connection shows "Connected" (local Windows hosting)

---

## Next Steps

1. **Test thoroughly** with paper trading
2. **Monitor NVIDIA usage** (stay within $25 free tier)
3. **Configure notifications** (WhatsApp, Discord, etc.)
4. **Set up alerts** (UptimeRobot + Sentry)
5. **Configure trading caps** (protect your portfolio)
6. **Link Exness account** (for Forex/CFD trading)
7. **Switch to live trading** when ready (uncheck Paper Trading)

---

**🎉 Congratulations! Jasper Trades is deployed!**

For support:
- Render logs: Dashboard → Logs
- Vercel logs: Deployments → View logs
- API docs: `https://YOUR_BACKEND.onrender.com/docs`

**Happy Trading! 📈🚀**