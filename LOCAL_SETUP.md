# Local PC setup — frontend + backend + Kronos, live data, Supabase persistence, Telegram alerts

## 1. One-time prerequisites
- Windows + PowerShell, Python 3.11+ (`py --version`), Node.js 18+ (`node --version`)
- Git clone this repo. Optional: Docker (only if you prefer containerized Kronos).

## 2. Configure `backend/.env`
- **Supabase persistence (recommended):** create a project at https://supabase.com → Project Settings → Database → Connection string → copy the **Transaction pooler (port 6543)** string and paste it as:
  ```
  DATABASE_URL="postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:6543/postgres"
  ```
  URL-encode the password. Migrations create the schema automatically on boot — no SQL editor needed.
  (SQLite fallback: `DATABASE_URL="sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"`)
- **Live market data:** works keyless out of the box (CoinGecko → CCXT → CoinLore). Optional keys for more: `COINGECKO_API_KEY` (demo), `FINNHUB_KEY`, `ALPHAVANTAGE_KEY`, `BIRDEYE_API_KEY`, `HELIUS_API_KEY`.
- **LLM (AI brain):** `GROQ_API_KEY` is already set. Optional side-by-side providers: `GEMINI_API_KEY`, `NVIDIA_API_KEY` (or plug them in Settings → AI engine; the app pings the key and lists authorized models).
- **Telegram alerts (trade + error messages):** create a bot at https://t.me/BotFather → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN=` in `backend/.env`. Then in Telegram: message your bot `/start` and complete the verification code the app shows in Settings → Telegram.
- **Brokers:** for forex/CFD demo/live connect MT5/MT4 in Settings → Connect (manual credentials or broker OAuth if `MT5_OAUTH_*` set). Crypto via CCXT keys in Settings; Solana wallet + `jupiter_enabled` for memecoins.

## 3. Run everything locally
```powershell
powershell -ExecutionPolicy Bypass -File ./start-all.ps1
```
This starts three windows:
- **Kronos forecaster** → http://localhost:8001 (downloads models on first run; `KRONOS_SERVICE_URL` points the backend at it)
- **Backend API** → http://localhost:8000 (docs at http://localhost:8000/docs)
- **Frontend** → http://localhost:3000

First run installs Python deps (incl. PyTorch CPU for Kronos) and npm packages — can take several minutes.

## 4. Verify
```powershell
python backend/scripts/deploy_smoke.py http://localhost:8000
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/system/pipeline-status
```
Open http://localhost:3000 → choose Paper mode in Settings → press **Start** on Home. The agent populates the watchlist with the top 15 performers, rotates it hourly, and trades in sandbox (paper). Switch environment to **Demo** (with an MT demo account connected) or **Live** in Settings → Broker Environment.

## 5. Telegram notifications
With `TELEGRAM_BOT_TOKEN` set and your chat verified, you get: trade opened/closed with PnL, daily summary (8 PM WAT), whale alerts, and **error alerts** (boot-step failures, auto-executor tick errors, scheduler task failures). Chat commands: `/status`, `/portfolio`, `/trades`, `/settings`, `/help`.

## Troubleshooting
- Port busy: change `PORT` / frontend port in `start-all.ps1`.
- Kronos model download fails: re-run; or point `KRONOS_SERVICE_URL` at a hosted Kronos service instead.
- Supabase connection fails: check the pooler string, password encoding, and that your IP is allowed (Supabase allows all by default).
