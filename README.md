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

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (in a second terminal)
cd frontend
npm install
npm run dev
```

- Frontend → http://localhost:3000
- Backend API → http://localhost:8000 (docs at `/docs` in dev only; disabled in production)

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
**Google Gemini 2.5 Flash** model with multi-key rotation so it never stalls on
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
│   │   ├── services/   LLM (Gemini+rotation), geo-probe, paper trading,
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
GEMINI_API_KEY=key1,key2,key3        # ~3 keys from separate Google accounts (PRIMARY LLM)
NVIDIA_API_KEY=                        # NVIDIA NIM fallback (used automatically if Gemini is down)
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

## 📚 Documentation

| Doc | Purpose |
|---|---|
| **DEPLOYMENT.md** | Full Render deployment + all free API keys |
| **README.md** (this) | Overview & quick start |
| **plan.md** | Architecture + roadmap |

---

## 🗺️ Roadmap

- [x] Gemini 2.5 Flash LLM with multi-key rotation
- [x] Nigeria-first market data (CoinGecko→CCXT→CoinLore) + geo-probing
- [x] cTrader live + Universal Paper Trading (all paper)
- [x] Solana memecoins (DexScreener discovery + Jupiter execution)
- [x] Telegram trade notifications
- [x] Responsive UI + guided onboarding tours
- [ ] Full UI restructure polish & strategy marketplace
- [ ] Reinforing-learning signals (FinRL, separate Render service)

---

**📈 Start in Paper Lab** → connect Telegram → let the AI wow you. Upgrade to
real trading on cTrader only when you're comfortable.

*Built with Next.js 15, FastAPI, Gemini 2.5 Flash, cTrader, CCXT, Solana.*
