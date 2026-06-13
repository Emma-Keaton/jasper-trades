# Jasper Trades - Installation & Setup Guide

## Quick Start (Windows)

### Prerequisites
- **Node.js 18+** (recommended: 20+) - [Download](https://nodejs.org/)
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Git** (optional, for version control)

### One-Command Install & Run

#### Option A: Using the install scripts

```bash
# 1. Install backend dependencies
cd backend
pip install -r requirements.txt

# 2. Copy environment files
copy .env.example .env

# 3. Install frontend dependencies
cd ..\frontend
npm install

# 4. Copy frontend environment file
copy .env.example .env.local
```

#### Option B: Automated install (Windows PowerShell)

```powershell
.\install.ps1
```

## Configuration

### Backend Configuration (`backend/.env`)

Edit `backend/.env` with your API keys:

```env
# NVIDIA NIM API (Required for AI features)
# Get your key from: https://build.nvidia.com/
NVIDIA_API_KEY=nvapi-your-key-here

#  Paper Trading (Free, no account minimum)
# Sign up: https://.markets/

# Optional: Binance for crypto
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Security (change in production!)
SECRET_KEY=change-this-to-random-secret-key
API_AUTH_KEY=change-this-auth-key
```

### Frontend Configuration (`frontend/.env.local`)

Edit `frontend/.env.local`:

```env
# Backend API URL (default: localhost:8000)
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket URL (optional, defaults to API URL)
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# NVIDIA NIM API Key (optional, for client-side AI features)
NEXT_PUBLIC_NVIDIA_API_KEY=
```

## Running the Application

### Terminal 1: Start Backend

```bash
cd backend

# Initialize database and start server
python -m app.main

# Alternative: Run with uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run on: **http://localhost:8000**  
API Docs: **http://localhost:8000/docs**

### Terminal 2: Start Frontend

```bash
cd frontend
npm run dev
```

Frontend will run on: **http://localhost:3000**

## First Run Checklist

1. ✅ Backend running on http://localhost:8000
2. ✅ Frontend running on http://localhost:3000
3. ✅ NVIDIA NIM API key configured in `backend/.env`
4. ✅ Database initialized (auto-created on first run)
5. ✅ Default portfolio created with $100K paper trading capital

## Troubleshooting

### Backend won't start

**Error: ModuleNotFoundError**
```bash
pip install -r requirements.txt --upgrade
```

**Error: Database locked**
```bash
# Delete and recreate database
del data\sqlite\jasper_trades.db
python -m app.main
```

### Frontend won't start

**Error: Node modules missing**
```bash
npm install
```

**Error: Port 3000 in use**
```bash
# Use different port
set PORT=3001
npm run dev
```

### Backend API not responding

1. Check if backend is running: http://localhost:8000/docs
2. Verify `NEXT_PUBLIC_API_URL` in `frontend/.env.local`
3. Check for CORS errors in browser console

### Connection Disconnected (red indicator)

This means the frontend can't reach the backend. Verify:
1. Backend is running
2. No firewall blocking port 8000
3. `NEXT_PUBLIC_API_URL` is correct

## Features Walkthrough

### Dashboard Tab
- Real-time portfolio value
- Active holdings with P&L
- Agent status overview
- Recent trade history
- Interactive equity chart

### Agents Tab
- Start/stop AI agents
- Configure model parameters
- View agent performance metrics
- Select LLM model routing

### Signals Feed
- Real-time AI trading signals
- Filter by agent, asset, type
- Execute trades directly from signals
- Add symbols to watchlist

### Copy Trading
- View top trader leaderboard
- Follow successful traders
- Track copied positions
- Monitor copy P&L

### Backtests
- Run historical simulations
- Select alpha factors
- View performance metrics
- Compare vs benchmark

### Alpha Zoo
- Browse 452+ pre-built factors
- View factor formulas
- Add to backtest strategy
- Save favorites

### Portfolio
- Holdings allocation view
- Trade history export (CSV)
- Position management
- Performance analytics

### Settings
- API key management
- Broker connections
- LLM model selection
- Notification preferences

## Deployment Options

### Local Network Access

To access from other devices on your network:

**Backend:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
set HOST=0.0.0.0
npm run dev
```

Then access via your machine's IP: `http://YOUR_IP:3000`

### Cloudflare Tunnel (Share Locally Running App)

```bash
# Install cloudflared
winget install Cloudflare.cloudflared

# Create tunnel to localhost:3000
cloudflared tunnel --url http://localhost:3000
```

Get a public HTTPS URL to share temporarily.

### Production Deployment (Vercel + PythonAnywhere)

See full deployment guide in `DEPLOYMENT.md`

## API Endpoints Reference

### Health & Status
- `GET /api/v1/status` - System health
- `GET /api/v1/system/tasks` - Background tasks

### Portfolio
- `GET /api/v1/portfolio` - List portfolios
- `GET /api/v1/portfolio/{id}` - Get portfolio
- `GET /api/v1/portfolio/{id}/holdings` - Get holdings
- `GET /api/v1/portfolio/{id}/trades` - Get trades
- `POST /api/v1/portfolio` - Create portfolio

### Trading
- `POST /api/v1/trading/execute` - Execute trade
- `POST /api/v1/trading/{id}/cancel` - Cancel trade
- `GET /api/v1/trading/history` - Trade history

### Signals
- `GET /api/v1/signals` - List signals
- `GET /api/v1/signals/active` - Active signals
- `POST /api/v1/signals/{id}/ack` - Acknowledge
- `POST /api/v1/signals/{id}/execute` - Execute from signal

### Agents
- `GET /api/v1/agents` - List agents
- `POST /api/v1/agents/{id}/start` - Start agent
- `POST /api/v1/agents/{id}/stop` - Stop agent

## Next Steps

1. **Paper Trading**: Start with the default $100K paper portfolio
2. **Configure Agents**: Set up your AI agents in the Agents tab
3. **Monitor Signals**: Watch the Signals Feed for trade ideas
4. **Run Backtests**: Test strategies before deploying capital
5. **Copy Trading**: Follow top performers automatically

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review API docs: http://localhost:8000/docs
3. Check logs in `backend/logs/` and browser console

---

**Jasper Trades** - AI-Powered Trading Platform