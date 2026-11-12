# Jasper Trades — AI-Powered Trading Platform (Nigeria-First)

**A simplified, onboarding-guided AI trading assistant for non-traders. It watches
crypto, forex and shares for you, explains its moves, and tells you about every
trade it makes through your connected Telegram chat.**

Built for beginners: no trading jargon required, guided setup wizards on every
screen, and a universal paper-trading mode so you can watch the AI trade with
practice money before risking anything real.

> ⚠️ Educational tool. Not financial advice. Never risk money you can't afford to lose.

---

## 🚀 Quick Start

### Automated Setup (Recommended)

```bash
# Run the complete setup script (installs all dependencies, configures env, initializes DB)
cd E:\Projects\jasper-trades
python setup.py --dev
```

The setup script will:
- ✅ Check Python 3.11+ and Node.js 20+
- ✅ Create Python virtual environment (`backend/.venv`)
- ✅ Install all Python dependencies (including Kronos local model with PyTorch CPU)
- ✅ Install Node.js frontend dependencies
- ✅ Generate secure secret keys (SECRET_KEY, API_AUTH_KEY, CTRADER_ENCRYPTION_KEY)
- ✅ Create `.env` files from templates
- ✅ Initialize SQLite database
- ✅ Download Kronos model from Hugging Face (optional, for local inference)
- ✅ Run test suite (skips slow integration tests)

---

### Manual Setup (Alternative)

If you prefer manual control or the automated script has issues:

**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# On Linux/macOS: source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# For Kronos local inference (optional, requires ~2GB download):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install huggingface_hub safetensors

# Configure environment
copy .env.example .env
# Edit .env with your API keys (see Required Setup below)

# Initialize database
python start_server.py

# Start backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (in a second terminal):**
```bash
cd frontend
npm install
npm run dev
```

### Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (dev only) | http://localhost:8000/docs |

---

### Setup Script Options

```bash
python setup.py [OPTIONS]

Options:
  --dev              Development mode (default)
  --prod             Production mode (builds frontend)
  --skip-frontend    Skip frontend setup
  --skip-backend     Skip backend setup
  --skip-kronos      Skip Kronos local model installation (use fallback forecaster)
  --skip-tests       Skip running test suite
  --only-deps        Only install dependencies (skip env setup, DB init, tests)
  --help             Show this help message
```

### Examples

```bash
# Full development setup (default)
python setup.py --dev

# Production setup with frontend build
python setup.py --prod

# Backend only (no frontend)
python setup.py --skip-frontend

# Skip Kronos local model (use statsmodels/deterministic fallback)
python setup.py --skip-kronos

# Quick dependency install only
python setup.py --only-deps
```

---

## ✨ What This App Does (in plain language)

| You will... | Where |
|---|---|
| Watch the AI trade before going live | **Paper Lab** (universal paper trading, practice money) |
| Connect your Telegram to get notified of every trade | **Settings → Telegram** |
| Connect a real broker for live trading | **Settings → Connect cTrader** |
| Ask simple questions ("Should I buy BTC?") | **AI Chat** (bottom-right) |
| Learn the app step-by-step | Built-in **guided tutorials** on every screen |

### 🤖 The AI Trader (4-stage pipeline)
A `Director → Quant → Risk → Execution` agent pipeline (powered by the free
**Groq** models with multi-key rotation so it never stalls on
rate limits) analyzes markets, scores opportunities, checks risk, then executes.

### 💱 Trading & Execution
- **Live trading** → **cTrader** (forex + shares; Nigerian-accessible brokers).
- **Live crypto** → **CCXT** on a Nigeria-accessible exchange (default **Bybit**),
  plus **Solana on-chain** for SPL tokens and memecoins.
- **Paper trading** (all assets) → the **Universal Paper Trading engine** — test
  the AI risk-free before going live.

### 📊 Market Data (Nigeria-safe, priority-chained)
**CoinGecko (default) → CCXT (Bybit/Binance) → CoinLore (fallback)**. The app
runtime-probes every data/broker source from its region and automatically
prunes any service that is geo-blocked or unreachable (including Binance and
Polymarket unless they respond).

### 🔔 Notifications
- **Telegram** — two-way chat + a message for **every executed trade**.
- Email (SendGrid), Discord for summaries and risk alerts.

### 🛡️ Safety
- Trading caps, circuit breakers, and **paper-first** execution.
- cTrader OAuth tokens encrypted at rest (one key, fail-closed).
- Real wallet connections are **signature-verified** (a pasted address can't be saved).

---

## 🏗️ Architecture

```
jasper-trades/
├── backend/            FastAPI + Python 3.11
│   ├── app/
│   │   ├── agents/     4-stage AI pipeline (Director→Quant→Risk→Execution)
│   │   ├── brokers/    cTrader (live), CCXT (crypto), Solana, Trove, AKShare
│   │   │               CCXT data, CoinLore, Solana memecoins, market data
│   │   ├── api/v1/     REST routes (incl. /geo, /paper, /memecoin)
│   │   └── schedulers/ cTrader token refresh
│   └── kronos-service/ Optional separate Render service for price forecaster
├── frontend/           Next.js 15 + React 19 + Tailwind (mobile/tablet/desktop)
│   ├── components/     Tabs + onboarding tutorials + responsive nav
│   └── lib/            API client, constants, WebSocket
└── data/               SQLite database
```

### Deployment (Render-only)
- **Main app** — free web service (FastAPI + Next.js).
- **Separate Render services** for RAM-heavy jobs: `kronos-service`, `rd-agent`,
  `finrl`. **No Colab is used.**

---

## 🔑 Required Setup (one-time)

Set these in your `.env` / Render dashboard:

```
GROQ_API_KEY=key1,key2,key3         # Groq keys (PRIMARY LLM)
CTRADER_CLIENT_ID=                     # cTrader Connect app
CTRADER_CLIENT_SECRET=
CTRADER_REDIRECT_URI=
CTRADER_ENCRYPTION_KEY=               # Fernet key for token encryption
TELEGRAM_BOT_TOKEN=                   # for trade alerts + chat
CCXT_EXCHANGES=bybit,okx,...          # Nigeria-accessible CEX set (geo-probe prunes)
SECRET_KEY=                           # strong random string
```

See **DEPLOYMENT.md** for the full guide and free-tier signup links.

---

### 📋 Step-by-Step: How to Get Each Secret/API Key

#### 1. **GROQ_API_KEY** (Required - Primary LLM)
**Free tier available** — Multiple keys recommended for rotation.

| Step | Action |
|------|--------|
| 1 | Go to https://console.groq.com/keys |
| 2 | Sign up / log in (free) |
| 3 | Click **"Create API Key"** |
| 4 | Name it (e.g., `jasper-trades-prod`) |
| 5 | Copy the key (starts with `gsk_`) |
| 6 | **Repeat 2-3 times** for multiple keys (rotation avoids rate limits) |
| 7 | In `.env`: `GROQ_API_KEY=gsk_xxx,gsk_yyy,gsk_zzz` (comma-separated) |

> **Why multiple keys?** Groq has per-key rate limits. The app rotates keys automatically so you never hit limits during active trading.

---

#### 2. **TELEGRAM_BOT_TOKEN** (Required - Trade Alerts + Chat)
**Free** — Used for notifications and two-way chat.

| Step | Action |
|------|--------|
| 1 | Open Telegram, search for **@BotFather** |
| 2 | Send `/newbot` |
| 3 | Choose a name: `Jasper Trades` |
| 4 | Choose a username ending in `bot`: `myjaspertrades_bot` |
| 4 | Copy the token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`) |
| 5 | In `.env`: `TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz` |
| 6 | **Get your Chat ID**: Message your bot, then visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` |
| 7 | Look for `"chat":{"id":123456789}` — that's your `TELEGRAM_CHAT_ID` |

---

#### 3. **CTRADER_CLIENT_ID / CTRADER_CLIENT_SECRET** (Required for Live Forex/Stocks)
**Free** — cTrader Connect OAuth app for multi-tenant copy trading.

| Step | Action |
|------|--------|
| 1 | Go to https://connect.spotware.com/ |
| 2 | Log in with your cTrader account (or create one) |
| 3 | Go to **"My Applications"** → **"Create New Application"** |
| 4 | **Application Type**: `Web Application` |
| 5 | **Redirect URI**: `http://localhost:8000/api/v1/brokers/ctrader/callback` (dev) or `https://your-app.onrender.com/api/v1/brokers/ctrader/callback` (prod) |
| 6 | **Scopes**: Select `openid`, `profile`, `email`, `trade`, `offline_access` |
| 7 | Click **Create** |
| 8 | Copy **Client ID** → `CTRADER_CLIENT_ID` |
| 9 | Copy **Client Secret** → `CTRADER_CLIENT_SECRET` |
| 10 | In `.env`: Set both values |

> **Sandbox vs Live**: Set `CTRADER_SANDBOX=true` for demo accounts. Change to `false` only when ready for real money.

---

#### 4. **CTRADER_REDIRECT_URI** (Required for cTrader OAuth)
Must **exactly match** what you registered in cTrader Connect.

| Environment | Value |
|-------------|-------|
| **Local Dev** | `http://localhost:8000/api/v1/brokers/ctrader/callback` |
| **Render (Production)** | `https://your-app.onrender.com/api/v1/brokers/ctrader/callback` |
| **Vercel (Frontend)** | Not needed here — only backend uses this |

> ⚠️ **Must match exactly** — including protocol (http/https), domain, path, and no trailing slash differences.

---

#### 5. **CTRADER_ENCRYPTION_KEY** (Required - Token Encryption)
**Auto-generated by setup.py** — Encrypts OAuth tokens at rest.

| Step | Action |
|------|--------|
| 1 | Run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| 2 | Copy the 44-char output (e.g., `abc123xyz...==`) |
| 3 | In `.env`: `CTRADER_ENCRYPTION_KEY=abc123xyz...==` |

> ⚠️ **Never lose this!** If lost, all stored cTrader tokens become invalid. Store securely (password manager).

---

#### 6. **CCXT_EXCHANGES** (Optional - Crypto Trading)
**Free** — Nigeria-accessible crypto exchanges. App geo-probes and prunes blocked ones.

| Step | Action |
|------|--------|
| 1 | Create accounts on Nigeria-accessible exchanges: **Bybit**, **OKX**, **Gate.io**, **MEXC** |
| 2 | Generate **API Key + Secret** on each exchange (enable **Spot Trading**, **Read-Only** for safety) |
| 3 | In `.env`: `CCXT_EXCHANGES=bybit,okx,gateio,mexc` (comma-separated, no spaces) |

> The app runtime-probes each exchange from your region and auto-prunes geo-blocked ones.

---

#### 7. **BINANCE_API_KEY / BINANCE_API_SECRET** (Optional - Binance)
**Free** — Only if Binance works in your region.

| Step | Action |
|------|--------|
| 1 | Go to https://binance.com/my/settings/api-management |
| 2 | Create API Key (enable **Spot**, **Futures** if needed) |
| 3 | **IP Whitelist**: Add your server IP (Render gives static IPs on paid plans) |
| 4 | In `.env`: Set both `BINANCE_API_KEY` and `BINANCE_API_SECRET` |

---

#### 8. **SECRET_KEY** (Required - Session/Auth)
**Auto-generated by setup.py** — Strong random string for sessions.

| Step | Action |
|------|--------|
| 1 | Run: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| 2 | Copy output (e.g., `abc123...`) |
| 3 | In `.env`: `SECRET_KEY=abc123...` |

---

#### 9. **API_AUTH_KEY** (Optional - Internal API Auth)
**Auto-generated by setup.py** — For service-to-service calls.

| Step | Action |
|------|--------|
| 1 | Run: `python -c "import secrets; print('jasper_' + secrets.token_urlsafe(16))"` |
| 2 | Copy output (e.g., `jasper_abc123...`) |
| 3 | In `.env`: `API_AUTH_KEY=jasper_abc123...` |

---

#### 10. **KRONOS_SERVICE_URL / KRONOS_API_KEY** (Optional - Time-Series Forecasting)
**Modal deployment required** — Model too large for Render free tier.

| Step | Action |
|------|--------|
| 1 | Deploy Kronos on Modal: `cd modal-kronos && modal deploy modal_app.py` |
| 2 | Copy the HTTPS endpoint URL |
| 3 | In `.env`: `KRONOS_SERVICE_URL=https://modal-kronos--web-xxx.modal.run` |
| 4 | Generate API key: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| 5 | In `.env`: `KRONOS_API_KEY=<generated_key>` |

> Without this, the app uses a local fallback forecaster (statsmodels/deterministic) — no sampled trajectories, no calibration.

---

#### 11. **SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY** (Recommended for Production)
**Free tier** — Persistent Postgres database.

| Step | Action |
|------|--------|
| 1 | Create project at https://supabase.com |
| 2 | **Settings → Database → Connection String** → Copy **Transaction Pooler** (port 6543) |
| 2 | Replace `{db_password}` with your DB password (URL-encoded) |
| 3 | Set as `DATABASE_URL` |
| 4 | **Settings → Data API** → Copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |

---

See **DEPLOYMENT.md** for the full guide and free-tier signup links.

### Quick Key Generation

The setup script auto-generates secure keys, but you can also generate manually:

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# API_AUTH_KEY
python -c "import secrets; print('jasper_' + secrets.token_urlsafe(16))"

# CTRADER_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🧪 Kronos Local Inference (Optional)
   ```
   KRONOS_SERVICE_URL=  # Leave empty for local inference
   KRONOS_API_KEY=      # Not needed for local
   ```

**Note:** Without Kronos, the system uses a tiered fallback forecaster (statsmodels → deterministic) that provides directional predictions but no sampled trajectories for calibration.

---

## 📚 Documentation

| Doc | Purpose |
|---|---|
| **DEPLOYMENT.md** | Full Render deployment + all free API keys |
| **README.md** (this) | Overview & quick start |
| **plan.md** | Architecture + roadmap |

---

## 🗺️ Roadmap

- [x] Groq LLM with multi-key rotation
- [x] Nigeria-first market data (CoinGecko→CCXT→CoinLore) + geo-probing
- [x] cTrader live + Universal Paper Trading (all paper)
- [x] Solana memecoins (DexScreener discovery + Jupiter execution)
- [x] Telegram trade notifications
- [x] Responsive UI + guided onboarding tours
- [x] Complete setup script (`setup.py`) with automated dependency installation
- [ ] Full UI restructure polish & strategy marketplace
- [ ] Reinforing-learning signals (FinRL, separate Render service)

---

**📈 Start in Paper Lab** → connect Telegram → let the AI wow you. Upgrade to
real trading on cTrader only when you're comfortable.

