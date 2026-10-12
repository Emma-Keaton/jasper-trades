# Jasper Trades - Complete Deployment Guide

## Authentication: the device UUID

There are **no user accounts**. A device's UUID is its credential.

The browser generates it once with `crypto.randomUUID()` (122 bits of CSPRNG
output), stores it in `localStorage` under `jasper_device_id`, and sends it on
every request as:

```
X-Device-ID: 3f2504e0-4f89-41d3-9a0c-0305e82c3301
```

Whoever presents that UUID *is* that device. It grants full read/write access to
that device's settings, portfolios, positions, trades, broker credentials and
payout wallet keys.

**The header is validated, not defaulted.** A missing or malformed
`X-Device-ID` returns `401`. There is no fallback identity — the previous
`x_device_id or "default-device"` meant any caller who omitted the header became
the same shared device. `API_AUTH_KEY` exists in `config.py` but nothing reads
it; the device UUID is the only authentication.

**Upgrading from an older build.** Devices previously held a 32-character
fingerprint rather than a UUID. The frontend detects this, mints a UUID, and
keeps the old value under `legacyDeviceId` in `jasper_device_info` so the
migration is visible. **That device's previous settings and history are not
carried over** — the new UUID is a new device.

### What this model does and does not give you

| | |
|---|---|
| Unauthenticated access | Denied — 401 without a valid UUID |
| Guessing another device | 122-bit CSPRNG UUID; not feasible |
| Cross-device data access | Prevented — portfolios are scoped by `device_id` |
| Revoking a device | **Not supported.** No server-side deny list |
| Leaked UUID | **Full access.** Treat it like a password |
| Public exposure | Unsuitable. Use an SSH tunnel or a private network |

**Before exposing this to the internet**, put it behind a private network or a
VPN. A leaked UUID cannot be revoked, and there is no second factor.

`SECRET_KEY` is still required: it derives the Fernet key that encrypts broker
credentials and the payout hot-wallet key at rest. It is not a request
credential, but the startup check refuses to boot in production without it.

---

## Quick Start (Local Testing)

There is no `start.bat` in this repository. Run the two servers in separate
terminals:

```bash
# Terminal 1 - backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - frontend
cd frontend
npm install
npm run dev
```

- **Backend**: http://localhost:8000 (API docs at `/docs`)
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
# Groq is the PRIMARY LLM. Set ~2-3 keys (comma-separated).
# separate Google accounts) so a rate-limited project never stalls a trade.
GROQ_API_KEY=key1,key2,key3
GROQ_BASE_URL=https://api.groq.com/openai/v1


# Groq model tiers
MODEL_FAST=qwen/qwen3.8-27b
MODEL_SMART=openai/gpt-oss-120b
MODEL_DEEP=openai/gpt-oss-120b

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
# The startup check refuses to boot in production if SECRET_KEY is the literal
# "change-this-in-production" or is shorter than 32 characters. Do not substitute
# another placeholder of the same length: a known key passes the length check and
# silently defeats session signing.
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=replace-with-a-real-random-32-plus-character-secret
# API_AUTH_KEY is NOT an authentication credential - nothing reads it.
# Authentication is the device UUID (see the Authentication section). Kept only
# so an existing deployment does not lose an unused setting.
API_AUTH_KEY=change-this-auth-key
CORS_ORIGINS="http://localhost:3000,http://localhost:8080"

# Environment. Must be "production" on a real deployment. It gates the
# production security check and, left as "development", auto-payouts never start.
ENVIRONMENT=development
DEBUG=true
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
│ Backend (Render)     - https://jasper-trades.onrender.com│
│ Telegram Bot (Bot API) - Runs inside backend            │
│ Groq - Free tier (multi-key rotation)             │
│ Kronos (Modal service)   - Price forecaster (separate)    │
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
   # Do NOT set PORT. Render injects it (8080). The repo's backend/.env.render
   # and config.py both expect 8080; hardcoding a different value fights the
   # platform and the health check.
   SECRET_KEY=<generate random 32+ chars; see the Quick Start warning>
   # API_AUTH_KEY is unused; see the Authentication section.
   ENVIRONMENT=production          # required for the production security check
   DEBUG=false                     # otherwise logs are not JSON and /docs stays on
   CORS_ORIGINS=https://jasper-trades.vercel.app
   WALLETCONNECT_PROJECT_ID=<your-walletconnect-project-id>  # optional; enables WalletConnect QR in Settings
   DATABASE_URL=postgresql://...   # see below; required, disk is wiped

   # Telegram (the bot and trade alerts stay disabled without a token)
   TELEGRAM_BOT_TOKEN=<from @BotFather>
   TELEGRAM_WEBHOOK_SECRET=<random string, required for webhook verification>

   # Auto-payouts (Part 3.3). Both are required: the scheduler only starts when
   # AUTO_PAYOUTS_ENABLED is true AND ENVIRONMENT is "production". Left off,
   # payout settings save fine and then nothing ever fires.
   AUTO_PAYOUTS_ENABLED=false
   ```

   `backend/.env.render` in this repo is the reference for the full list and
   also sets the rate-limit, HSTS/cookie, cTrader, Paystack/Flutterwave, and
   Groq variables.

   **Database — use Supabase for persistence (required).** Render free tier wipes
   its disk on every redeploy, so SQLite data is lost. This includes the Kronos
   prediction ledger and learned parameters: without Postgres, calibration
   evidence and learned thresholds reset to zero on every deploy and no model can
   ever be promoted. Supabase Postgres survives redeploys.

   **Provisioning the schema.** The app reconciles it on startup
   (`app/migrations.py`: `create_all` plus incremental `ADD COLUMN IF NOT
   EXISTS`), which is normally enough. To reach the same state from the Supabase
   SQL editor with no deploy — useful when the first deploy cannot start because
   the schema is missing a column it needs — apply the single generated file:

   ```bash
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/scripts/schema.sql
   ```

   `backend/scripts/schema.sql` is generated from the models and is
   non-destructive and re-runnable: on an empty project it builds all 43 tables
   (including the nine under `app/models_ext` — cTrader, Polymarket, broker
   connections), on an existing one it adds any column added since, and repeated
   runs are no-ops. Regenerate after a model change with
   `python backend/scripts/generate_schema.py`.

   To drop everything and start over — destructive, and kept as a separate
   explicit step so the schema file can never delete data by accident:

   ```bash
   python backend/scripts/reset_db.py "$DATABASE_URL"
   # or, with psql available:
   backend/scripts/reset.sh
   ```

   Both refuse to run unless the target actually contains jasper-trades tables.
   This replaces two earlier reset scripts that had drifted apart and omitted the
   `models_ext` tables.

   Use the **session pooler** (port `5432`) for a persistent web service. Note
   this differs from `backend/.env.example`, which documents port `6543` (the
   transaction pooler) — use `5432` here and change the port if you see
   `prepared statement` errors under load.

   ```
   DATABASE_URL=postgresql://postgres.<project-ref>:<db_password>@<region>.pooler.supabase.com:5432/postgres
   ```
   URL-encode any special characters in the password. The backend detects Postgres
   from the `postgresql://` scheme and uses the asyncpg driver; migrations run at
   startup.
   - Optional (only if you use realtime/auth/storage): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
   - If you skip Supabase, use `DATABASE_URL=sqlite+aiosqlite:///./data/sqlite/jasper_trades.db` and `DATA_DIR=./data` — data is then wiped on every redeploy.
   - ⚠️ **Auth note:** repeated wrong-password attempts trigger Supabase's circuit breaker (`ECIRCUITBREAKER: too many authentication failures`). Wait several minutes before retrying, and paste the exact dashboard password — do not add `[ ]` brackets around it.

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
   # Must match the backend hostname exactly, including the .com TLD, and must
   # be listed in the backend's CORS_ORIGINS.
   NEXT_PUBLIC_API_URL=https://jasper-trades.onrender.com
   NEXT_PUBLIC_WS_URL=wss://jasper-trades.onrender.com
   ```

4. **Deploy** - Click "Deploy" (2-5 minutes)

**Frontend URL:** `https://jasper-trades.vercel.app`

---

### Step 4: Configure via Settings Page

1. **Open Settings:** `https://jasper-trades.vercel.app/settings`

2. **Configure AI:**
   - **Groq (primary):** set `GROQ_API_KEY` in your Render dashboard variables. The Settings page reports "Groq ready" when configured.

3. **Configure Paper Trading (default, recommended for testing):**
   - Settings → Paper Trading → enable Practice mode
   - The Universal Paper Trading engine handles all assets risk-free
   - Switch to live only when you are comfortable (cTrader/CCXT/Trove/Tiger)

4. **Configure Notifications (Optional):**
   - **Telegram** - Bot token + chat ID (primary; two-way chat + trade alerts).
     Needs `TELEGRAM_BOT_TOKEN` in the environment as well as the Settings entry.
   - **Discord** - Paste webhook URL
   - **Email** - SendGrid configuration
   - **Slack** - Backend endpoint only (`POST /api/v1/notify/configure/slack`).
     There is **no Slack field in the Settings UI**.

---

## Part 3: Multi-Broker Setup

### Broker Routing

Jasper routes trades by asset class:

| Asset Class | Broker |
|-------------|--------|
| Stocks/Equities (US + Nigerian NGX) | Trove Finance |
| Crypto | CCXT exchange (Binance / Bybit / OKX, see `CCXT_EXCHANGES`) |

**These brokers are not active on a fresh deployment.** `initialize_brokers()`
is called at startup with no configuration, and the registry defaults are:

- **CCXT** registers only if Binance credentials are already present at import
  (`api_key` and `api_secret`), otherwise it logs
  `CCXT broker not initialized: missing Binance API credentials`.
- **Trove** and **Solana** default to `enabled: false` and are never registered.

Only `ctrader` and `akshare` register by default. On a fresh install every symbol
in the table above resolves to `None`, so orders have no broker to route to.

There is also no runtime re-registration: configuring a broker in the Settings
page persists credentials but does not register the broker for the current
process. Restart the service after adding broker credentials.

Note also that `backend/.env.example` marks the direct Binance path
"DEPRECATED for Nigeria - geo-blocked" and routes live crypto through CCXT
(Bybit/OKX).

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

## Part 3.25: Kronos Predictions

Kronos is a time-series forecasting model. It predicts prices and nothing else:
it holds no positions, reads no account state, and never decides to trade. This
backend owns market data, execution, outcomes, calibration, and which model is
active.

It runs on **Modal**, not Render: the model weights are far too large for a free
Render service, and a CPU container on Modal starts in seconds without a GPU
budget. See `E:\Projects\modal-kronos`.

### Configure the backend

Set these in `backend/.env` (or the Render service's environment):

```env
KRONOS_SERVICE_URL="https://<your-modal-endpoint>.modal.run"
KRONOS_API_KEY="<the shared key from the Modal service>"
```

`KRONOS_API_KEY` is **required**. The Modal service rejects unauthenticated
requests, so without it every forecast fails and the backend falls back to the
local forecaster.

**Replacement fallback:** when `KRONOS_SERVICE_URL` is blank, the key is missing,
or the service is unreachable, the backend falls back to a built-in tiered
forecaster (`app/services/forecasting/`, ported from aegis-quant): statsmodels
Holt-Winters when available, otherwise a dependency-free deterministic trend
forecaster (`numpy`). It fetches daily closes via Yahoo chart (keyless,
`data_connectors`) and returns a real `UP`/`DOWN` prediction with confidence.

The fallback is a **degraded** source, not an equivalent one. It produces no
sampled trajectories, so `LedgerStore.record_forecast` refuses it and it never
contributes to calibration. If the fallback is the only thing running, no model
will ever be promoted and no learned threshold will ever validate.

### Endpoints

```bash
# Health, including observed calibration
curl {KRONOS_SERVICE_URL}/health

# Forecast from a bare close series (the shape this backend uses)
curl -X POST {KRONOS_SERVICE_URL}/forecast/closes \\
  -H "X-API-Key: $KRONOS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"closes": [100.1, 100.4, ...], "horizon": 30, "samples": 10}'

# Forecast from full OHLCV candles
curl -X POST {KRONOS_SERVICE_URL}/forecast \\
  -H "X-API-Key: $KRONOS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"candles": [{"open":100,"high":101,"low":99,"close":100,"volume":12}, ...], "horizon": 30, "sample_count": 10}'

# Batch by symbol; the service fetches the bars itself
curl -X POST {KRONOS_SERVICE_URL}/forecast/batch \\
  -H "X-API-Key: $KRONOS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"symbols": ["AAPL", "TSLA"], "horizon": 24, "sample_count": 10}'
```

Routes are `GET /health`, `GET /`, `GET /forecast`, `POST /forecast`,
`POST /forecast/closes`, and `POST /forecast/batch`.

The two forecast routes use different field names, which is deliberate:
`/forecast/closes` takes `samples` (default 10) and `/forecast` takes
`sample_count` (default **1**). `sample_count=1` is accepted by the API, but a
single path carries no distributional information, so this backend's
`LedgerStore.record_forecast` refuses to record it and it never reaches
calibration. Use `samples=10` on `/forecast/closes`, or `sample_count>=2`
elsewhere.

### Calibration and model promotion

Kronos never learns. The prediction ledger in Postgres does:

1. **Record** every real, non-degenerate forecast (`kronos_forecasts`). Refused:
   fallback/replacement output, and anything with fewer than two trajectories.
2. **Score** each one against the realised close once its horizon elapses.
3. **Refit** hourly (`_refit_learned_parameters` in `app/services/scheduler.py`).
4. **Promote** a model only when its record beats a coin flip with statistical
   confidence: at least 60 scored forecasts, at least 25 in one confidence
   bucket, and a one-sided binomial test at `p < 0.05`.

Learned parameters and the active model are **workspace-global**. Kronos is the
same frozen forecaster for every device, so evidence from any device improves
the shared estimate. Keying this per device would leave everyone on defaults
indefinitely. Unvalidated state is persisted but **not applied** -- it is stored
so you can inspect it before it moves a real threshold.

### Kronos troubleshooting

**Every forecast fails with 403:** `KRONOS_API_KEY` is unset or does not match
the key configured on the Modal service.

**Every forecast fails with 404 or a connection error:** `KRONOS_SERVICE_URL` is
wrong. A Modal endpoint URL changes when the deployment is recreated; re-copy it
from `modal deploy`.

**Rate limited (429):** the Modal service uses a weighted token bucket. Bursting
requests will produce 429 and the client does not retry automatically.

**No model is ever promoted:** expected until enough evidence exists. Check
`GET /api/v1/system/kronos/stats` for `calibration.scored` and read the refit log
line. Promotion requires statistical significance, so a lightly used workspace
may legitimately never promote anything.

---

## Part 3.3: Auto-Payout Configuration (Flexible Profit Distribution)

### Overview

Auto-payout distributes a share of profit to a destination on a schedule.

**Two things must both be true or nothing ever fires.** The scheduler only
starts when `AUTO_PAYOUTS_ENABLED=true` **and** `ENVIRONMENT=production`
(`app/main.py`). Both default to off/`development`. With them unset, payout
settings save successfully and then silently do nothing; the only symptom is a
`Auto-payout scheduler not started` log line.

**Payout Destinations:**
1. **Crypto Wallet** - USDT transfers via Tatum
2. **Nigerian bank transfer** - NGN via Paystack/Flutterwave + Trove
   (`POST /api/v1/settings/payout/naira-bank`)

### Configuration Fields

The request body is **flat** (no `payout_config` wrapper). These are the fields
`PayoutSettingsRequest` accepts; unknown keys are silently ignored.

```json
{
  "payout_enabled": true,
  "payout_percentage": 50.0,
  "payout_schedule_hour": 20,
  "payout_schedule_minute": 0,
  "payout_frequency": "custom_time",
  "min_payout_threshold": 10.0,
  "crypto_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595f4bE83",
  "broker_account": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `payout_enabled` | boolean | Enable/disable auto-payout |
| `payout_percentage` | number (0-100) | % of daily profit to distribute |
| `payout_schedule_hour` | number (0-23) | Hour in **WAT (Africa/Lagos)** |
| `payout_schedule_minute` | number (0-59) | Minute within that hour |
| `payout_frequency` | string | `custom_time` or `end_of_trade` |
| `min_payout_threshold` | number | Minimum profit before payout triggers |
| `crypto_wallet` | string | USDT address (ERC20 `0x...`, or Solana base58) |
| `broker_account` | integer | Portfolio/broker account to pay from |

Two corrections to older versions of this guide:

- The schedule is evaluated in **WAT (Africa/Lagos)**, not ET
  (`app/services/payout_scheduler.py`). Configuring "8 PM ET" fires at 8 PM
  Lagos. The ET-based daily-*profit* window in `withdrawal_service.py` is a
  separate calculation and does not set the schedule.
- `crypto_chain` is a **frontend-only** field. It is used to validate the address
  client-side and is never sent in the save body. Chain selection on the backend
  is not implemented: a `0x` address is always treated as Ethereum, and
  wallet validation rejects anything but `ethereum`/`erc20`/`solana`/`spl`.
  **BSC is not supported** despite the `USDT_CONTRACT_BSC` constant existing.

### Prerequisites

**Crypto Wallet Payout:**
- Tatum API key (https://tatum.io)
- USDT wallet address (ERC20 or Solana)

**Tatum key storage:** the key is read **only** from the encrypted
`DeviceSettings.tatum_api_key` column. There is no `TATUM_API_KEY` environment
variable and no `.env` fallback. Adding it to `backend/.env` has no effect —
this is the single most common cause of "Tatum API not configured".

### Step 1: Configure Tatum API Key (For Crypto Payouts)

1. Go to https://tatum.io and create an account.
2. Generate an API key with ETH/SOL mainnet permissions.
3. In Jasper Trades Settings, open the Auto-Payout section and enter the key in
   the dedicated field. It is saved encrypted and served back to the UI
   pre-filled.

### Step 2: Set Payout Configuration

1. Go to Settings → Auto-Payout.
2. Toggle **Enable Auto-Payout** on.
3. Set the percentage (share of daily profit to distribute).
4. Set the destination and, for a crypto payout, the USDT address.
5. Set the schedule hour/minute (WAT) and the minimum threshold.
6. Click **Save Auto-Payout Settings**. (There is no separate "Test Payout"
   button; wallet validation has its own control, which calls
   `POST /api/v1/withdrawal/payout/validate-wallet`.)

### How It Works - Payout Flow

```
At the scheduled hour (WAT)
  ↓
Check: Profit > $0? → No → Skip
  ↓
Check: Profit > Threshold? → No → Skip
  ↓
Calculate: Payout Amount = Profit × (Percentage / 100)
  ↓
Route to destination
  ↓
Database audit trail (Withdrawal table)
  ↓
Notification (Telegram/Discord/Email if configured)
```

**Known limitation — portfolio selection.** The scheduler evaluates every
device's configuration against the **first** portfolio in the database
(`payout_scheduler.py`: `select(Portfolio).limit(1)`, annotated "for now, get
first portfolio"). On a multi-device deployment payouts can therefore be
computed against the wrong portfolio. Verify this before relying on payouts
with more than one device.

### API Endpoints

```bash
# Get payout configuration (fields are flat at the top level)
GET /api/v1/withdrawal/payout/settings
Headers: X-Device-ID: {device_id}

Response:
{
  "configured": true,
  "payout_enabled": true,
  "payout_percentage": 50.0,
  "payout_schedule_hour": 20,
  ...
}

# Save configuration (flat body, no wrapper)
POST /api/v1/withdrawal/payout/settings
Headers: X-Device-ID: {device_id}
Body: { "payout_enabled": true, "payout_percentage": 50.0, ... }

# Execute a payout immediately
POST /api/v1/withdrawal/scheduler/execute/{portfolio_id}
Response: { "success": true, "message": "..." }

# Validate a payout wallet address
POST /api/v1/withdrawal/payout/validate-wallet
```

The execute endpoint returns only `success` and `message`. It does **not**
return a `status`, `amount`, `destination`, or `tx_hash`; check the `withdrawal`
table or `/api/v1/withdrawal/history` for the transaction.

### Troubleshooting

**"Insufficient balance":**
- Portfolio cash < payout amount.
- Ensure trading profits have been realized (trades filled).

**"Tatum API not configured":**
- Re-enter the key in the Settings UI. Setting `TATUM_API_KEY` in `.env` does
  nothing — there is no such environment variable.

**"Already paid out today":**
- The system prevents duplicate daily payouts. Wait for the next window.

**"No profit available":**
- Daily PnL must be positive. Check trading activity in the portfolio.

**Settings save but nothing ever fires:**
- `AUTO_PAYOUTS_ENABLED` and `ENVIRONMENT=production` are both required. See the
  note at the top of this section.

### Monitoring & Audit

**View Payout History:**
```bash
# portfolio_id is required; the filter parameter is withdrawal_type, not type
GET /api/v1/withdrawal/history?portfolio_id={id}&withdrawal_type={type}
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

**Email templates actually implemented** (`app/services/sendgrid_service.py`):
- 📈 Trade execution confirmations
- 🔔 Price alert notifications
- 📊 Daily summary

There is **no weekly report** and **no daily-morning email**. The scheduled
"daily summary" is a Telegram push at 8 PM WAT (7 PM UTC), sent only when the
user's `TelegramUser.daily_summary_enabled` is true.

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
# Universal paper trading is ON by default. It is what the "Paper Trading Mode"
# toggle in Settings writes to. Per-portfolio is_paper overrides it.
UNIVERSAL_PAPER_TRADING=true
UNIVERSAL_PAPER_CAPITAL=10000
UNIVERSAL_PAPER_CURRENCY=USD
```

There is no `_PAPER` variable. An earlier version of this guide showed
`_PAPER=false`; that name appears nowhere in the code and setting it switches
nothing. `backend/.env.example` contains the same broken lines
(`_API_KEY=`, `_API_SECRET=`, `_PAPER=true`) — treat that file's underscore
entries as typos.

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
| **Groq** | Free tier | generous free tier | $0 (testing) |
| **Tatum** | Free tier | 100 transactions/month | $0 |
| **UptimeRobot** | Free | 50 monitors | $0 |
| **Total** | | | **$0/month** |

*With UptimeRobot keeping it awake 24/7

### Scaling Path (Paid)

| Upgrade | Cost | Benefit |
|---------|------|---------|
| **Render Standard** | $7/mo | Always-on, no cold starts |
| **Railway** | $5/mo | 2GB RAM, no sleep |

---

## Troubleshooting

### Backend Sleeps Despite UptimeRobot
- Check monitor is active: https://uptimerobot.com/dashboard
- Verify URL: `https://YOUR_BACKEND.onrender.com/api/v1/health`
- Ensure 5-minute interval (not 10)

### Telegram Not Working
1. Verify the bot token is configured in Settings → Telegram. The backend also
   reads `TELEGRAM_BOT_TOKEN` from the environment; without either, the bot is
   disabled at startup (`Telegram bot disabled` in the logs).
2. Check backend logs for Telegram webhook startup.
3. Test (this route is **POST**; a bare `curl` sends GET and returns 405):
   ```bash
   curl -X POST https://YOUR_BACKEND.onrender.com/api/v1/settings/telegram/test
   ```

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

`daily_loss_percentage` and `max_position_percentage` are **accepted and stored
but never enforced.** Only these caps are actually checked in `trade_gate.py`:

| Cap | Enforced? |
|-----|-----------|
| `max_position_amount` | Yes |
| `hard_limit` / `soft_limit` (trade frequency) | Yes |
| `daily_loss_limit` | Yes, but **only on `sell`** |
| `daily_loss_percentage` | **No** |
| `max_position_percentage` | **No** |

Two consequences worth knowing before you rely on them:

- Setting a daily-loss **percentage** gives no protection. Use the absolute
  `daily_loss_limit` instead.
- Because the daily-loss check is gated on `side == "sell"`, an open position can
  be closed out on a loss without that limit being consulted.

The daily-loss counter resets at **UTC midnight**, not midnight ET.

### Kronos / Memory

An earlier version of this section advised reducing batch size or using a
`kronos-mini-int8` model to fit in RAM. Both are obsolete: inference runs on the
separate modal-kronos service, not in this backend, and no `kronos-mini-int8`
identifier exists anywhere in the codebase. `config.py` says so explicitly — the
memory/RAM knobs there applied to an in-process torch model this backend no
longer runs. The models in use are `NeoQuasar/Kronos-mini` and `kronos-mini`.

---

## Security Checklist

- [ ] `SECRET_KEY` set to a real random value of 32+ characters
- [ ] `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Device UUID model understood; instance not publicly exposed (see Authentication)
- [ ] CORS_ORIGINS set to production domain
- [ ] `DATABASE_URL` points at Postgres (not SQLite on Render)
- [ ] `TELEGRAM_BOT_TOKEN` set if Telegram alerts are wanted
- [ ] Paper trading enabled for testing
- [ ] Supabase scheduled backups configured

### Not enforced despite being configurable

These are stored and returned by the API but never checked. Do not treat them as
risk controls:

- `daily_loss_percentage` — use `daily_loss_limit` instead
- `max_position_percentage` — use `max_position_amount`
- Slack notifications have a backend endpoint (`POST /api/v1/notify/configure/slack`)
  but no Settings UI

Also absent: a weekly performance report and a weekly email. The scheduled
"daily summary" is a **Telegram push at 8 PM WAT (7 PM UTC)**, sent only when the
user's `TelegramUser.daily_summary_enabled` is true — it is not an email and not
a weekly report.

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

### Database (Postgres on Supabase)

**There is no backup endpoint on this API.** `/api/v1/backup` does not exist —
an earlier version of this guide recommended
`curl .../api/v1/backup > backup.db`, which would have written a 404 JSON body
into a file named `backup.db`.

Back up the Postgres database instead:

- **Supabase dashboard:** Database → the active project → Backups, and enable
  scheduled backups. This is the recommended option and needs nothing from this
  app.
- **Command line:** `pg_dump "$DATABASE_URL" -Fc -f jasper_backup.dump`, then
  store the file outside Render. Render free tier has no automatic backups.

Do not use SQLite `backup.db` dumps against a Postgres deployment — they would
be meaningless.

### Settings (Encrypted)
Settings stored encrypted in database - export monthly via Settings page.

---

## Success Checklist

Your deployment is successful when:
- [✅] Frontend loads from Vercel
- [✅] Backend API responds from Render
- [✅] Telegram notifications work (if configured)
- [?] Groq API key configured
- [✅] Test trade executed (paper mode)
- [✅] Mobile access works
- [✅] Multi-broker routing functional
- [✅] Trading caps configured (risk management active)

---

## Next Steps

1. **Test thoroughly** with paper trading
2. **Monitor Groq usage** (stay within free tier rate limits)
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
