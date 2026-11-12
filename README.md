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

For local time-series forecasting without external API:

1. **Install PyTorch CPU:**
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
   pip install huggingface_hub safetensors
   ```

2. **Download Kronos model (auto-downloaded by setup.py):**
   ```bash
   python -c "
   from huggingface_hub import hf_hub_download
   hf_hub_download(repo_id='傲慢的狼队/Kronos', filename='kronos-mini.safetensors')
   hf_hub_download(repo_id='傲慢的狼队/Kronos', filename='kronos-mini-int8.safetensors')
   "
   ```

3. **Configure in .env:**
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

