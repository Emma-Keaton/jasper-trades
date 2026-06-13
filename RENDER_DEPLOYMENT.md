# Render Deployment Guide - Jasper Trades Backend

## Step-by-Step Deployment to Render

### Step 1: Push to GitHub (if not already done)

```bash
cd E:\Projects\jasper-trades
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

---

### Step 2: Create Render Account

1. Go to https://render.com/
2. Click **"Get Started for Free"**
3. Sign in with **GitHub** (recommended) or email
4. Verify your email

---

### Step 3: Create New Web Service

1. **Dashboard** → Click **"New +"** → **"Web Service"**
2. **Connect Repository:**
   - Click **"Connect a repository"**
   - Select **"jasper-trades"** from your GitHub repos
   - Click **"Connect"**

3. **Configure Service:**
   - **Name:** `jasper-backend` (or your choice)
   - **Region:** Choose closest to you (e.g., Oregon, Frankfurt)
   - **Root Directory:** `.` (root of repo)
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     sh render-build.sh
     ```
   - **Start Command:**
     ```bash
     python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** **Free** (512MB RAM, 0.5 CPU)

**Note:** The build script compiles both backend (Python) and frontend (Next.js), then serves the frontend from the backend.

---

### Step 4: Environment Variables

**Copy these into Render's Environment Variables section:**

```env
# ────────────────────────────────────────────────
# Application Settings
# ────────────────────────────────────────────────
PYTHON_VERSION=3.11.0
PORT=10000
DEBUG=false
APP_NAME="Jasper Trades"
APP_VERSION="1.0.0"

# ────────────────────────────────────────────────
# Database (SQLite - file-based, no setup needed)
# ────────────────────────────────────────────────
DATABASE_URL="sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"
DATA_DIR="./data"

# ────────────────────────────────────────────────
# Security - GENERATE NEW ONES FOR PRODUCTION!
# ────────────────────────────────────────────────
# Generate随机32+ character strings for these:
SECRET_KEY="<GENERATE_RANDOM_32_CHARS_HERE>"
API_AUTH_KEY="<GENERATE_RANDOM_AUTH_KEY_HERE>"

# ────────────────────────────────────────────────
# CORS - Add your frontend URL after deploying to Vercel
# ────────────────────────────────────────────────
CORS_ORIGINS="http://localhost:3000,http://localhost:5173"

# ────────────────────────────────────────────────
# NVIDIA NIM API - REQUIRED for AI features
# Get free API key: https://build.nvidia.com/
# ────────────────────────────────────────────────
NVIDIA_API_KEY="<PASTE_YOUR_NVIDIA_API_KEY_HERE>"
NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"

# ────────────────────────────────────────────────
# Model Routing (FREE tier verified)
# ────────────────────────────────────────────────
MODEL_FAST="nvidia/nemotron-mini-4b-instruct"
MODEL_BALANCED="moonshotai/kimi-k2.6"
MODEL_SMART="nvidia/nemotron-3-ultra-550b-a55b"
MODEL_DEEP="nvidia/nemotron-3-ultra-550b-a55b"

# ────────────────────────────────────────────────
#  Trading (Optional - can configure via UI later)
# Sign up: https://.markets/
# ────────────────────────────────────────────────

# ────────────────────────────────────────────────
# Binance (Optional)
# ────────────────────────────────────────────────
BINANCE_API_KEY=""
BINANCE_API_SECRET=""

# ────────────────────────────────────────────────
# Kronos AI Predictions (Optional - Colab integration)
# Get URL from kronos_colab.ipynb after running
# ────────────────────────────────────────────────
KRONOS_COLAB_URL=""
KRONOS_COLAB_STRATEGY="cascade"

# ────────────────────────────────────────────────
# HuggingFace (Optional - for Kronos models)
# ────────────────────────────────────────────────
HUGGINGFACE_API_TOKEN=""

# ────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────
LOG_LEVEL="INFO"
LOG_FORMAT="json"
```

---

### Step 4b: Configure Vercel Frontend Environment Variables

**After deploying backend to Render, configure your Vercel frontend:**

1. Go to your Vercel dashboard → Select your frontend project
2. Navigate to **Settings** → **Environment Variables**
3. Add these variables:

```env
# Backend API URL (HTTPS - for REST API calls)
NEXT_PUBLIC_API_URL=https://jasper-backend-<RANDOM_ID>.onrender.com

# WebSocket URL (WSS - for real-time price updates)
# IMPORTANT: Use 'wss://' (secure WebSocket) for production
NEXT_PUBLIC_WS_URL=wss://jasper-backend-<RANDOM_ID>.onrender.com
```

4. Click **Save** and **Redeploy** the frontend

---

### Step 5: Generate Secret Keys

**For `SECRET_KEY`:**
```python
# Run this in Python to generate:
import secrets
print(secrets.token_urlsafe(32))
# Example output: vK8j2Lm9pQ3xR7nF4wT6yH1zC5bN0aE8dS2uV9iG3oP
```

**For `API_AUTH_KEY`:**
```python
import secrets
print("jasper_" + secrets.token_urlsafe(16))
# Example output: jasper_7xR3mN9pL2qK8vT4
```

---

### Step 6: Deploy

1. Click **"Create Web Service"** at bottom
2. Render will:
   - Build your backend (~2-5 minutes)
   - Deploy and start the service
   - Show logs in real-time
3. When you see **"✅ Your service is live"** → Deployment complete!

**Your backend URL will be:**
```
https://jasper-backend-<RANDOM_ID>.onrender.com
```

---

### Step 7: Test Backend

**Test Health Endpoint:**
```bash
curl https://YOUR_BACKEND_URL.onrender.com/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Jasper Trades API",
  "version": "1.0.0"
}
```

**Test NVIDIA API Integration:**
```bash
curl https://YOUR_BACKEND_URL.onrender.com/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the market sentiment today?"}'
```

---

### Step 8: Prevent Render Free Tier Sleep

**Render free tier sleeps after 15 minutes of inactivity.**

**Option 1: UptimeRobot (Recommended - Free)**
1. Go to https://uptimerobot.com/
2. Create free account
3. **Add Monitor:**
   - Type: **HTTP(s)**
   - URL: `https://YOUR_BACKEND.onrender.com/api/v1/health`
   - Check interval: **5 minutes**
4. Save → Backend stays awake 24/7

**Option 2: Upgrade to Render Paid ($7/month)**
- No sleep
- More RAM (1GB)
- Auto-deploy on git push

---

### Step 9: Configure Via Settings Page

**After deployment, configure broker/API keys via the UI:**

1. Go to your frontend (local or Vercel)
2. **Settings Page** → Configure:
   - **NVIDIA NIM API** - Paste API key, test, save
   - ** Trading** - Enter API keys for paper/live trading
   - **Binance** - Crypto trading (optional)
   - **Notifications** - WhatsApp, Discord, Email (optional)
   - **Kronos Colab** - Paste Colab URL for AI predictions

**All settings saved to database** - no need to re-deploy!

---

## Environment Variables Quick Reference

| Variable | Required? | Example | Description |
|----------|-----------|---------|-------------|
| `PYTHON_VERSION` | ✅ | `3.11.0` | Python version for Render |
| `PORT` | ✅ | `10000` | Render-provided port |
| `SECRET_KEY` | ✅ | `vK8j2Lm9...` | 32+ char random string |
| `API_AUTH_KEY` | ✅ | `jasper_7xR3...` | Auth token for API |
| `NVIDIA_API_KEY` | ✅ | `nvapi_xxxxx` | Get from https://build.nvidia.com |
| `MODEL_FAST` | ✅ | `nvidia/nemotron-mini-4b-instruct` | Free tier model |
| `_PAPER` | ✅ | `true` | true=paper, false=live |
| `CORS_ORIGINS` | ⚠️ | `https://frontend.vercel.app` | Your frontend URL |
| `DATABASE_URL` | ⚠️ | `sqlite+aiosqlite:///./data/...` | SQLite file path |
| `_API_KEY` | Optional | `PK_xxxxx` | Paper/live trading |
| `KRONOS_COLAB_URL` | Optional | `https://xxx.ngrok.io` | AI predictions |

**Legend:**
- ✅ = Required for deployment
- ⚠️ = Required for production (can use defaults for testing)
- Optional = Configure via Settings UI later

---

## Troubleshooting

### "Service failed to start"

1. **Check Logs:**
   - Render Dashboard → Your Service → **Logs** tab
   - Look for Python errors or missing dependencies

2. **Common Issues:**
   - **No requirements.txt:** Ensure `backend/requirements.txt` exists
   - **Port mismatch:** Start command uses `$PORT` env variable
   - **SQLite permissions:** `DATA_DIR=./data` must be writable

### "NVIDIA API returns 401"

- Missing or invalid `NVIDIA_API_KEY`
- Get new key from https://build.nvidia.com/
- Verify key in Settings page → Test button

### "Database is locked"

- SQLite file corruption
- **Fix:** Delete `data/sqlite/jasper_trades.db` via SSH or re-deploy

### "CORS error from frontend"

- Update `CORS_ORIGINS` in Render env vars
- Add your Vercel/localhost URL:
  ```
  CORS_ORIGINS="https://jasper-trades.vercel.app,http://localhost:3000"
  ```

---

## Cost Estimation

| Service | Free Tier | Paid Option |
|---------|-----------|-------------|
| **Render Backend** | 500 hours/month (~20 days) | $7/month (unlimited) |
| **UptimeRobot** | Unlimited (5 min checks) | $6.50/month (1 min checks) |
| **NVIDIA NIM API** | $25 credits/month | Pay-as-you-go (~$0.20-2.00/1M tokens) |
| **Total (Testing)** | **$0/month** | **$7-15/month** |

**Note:** 500 hours = backend sleeps 10 hours/month. Use UptimeRobot to prevent sleep.

---

## Next Steps

1. **Deploy Frontend to Vercel** (separate guide)
2. **Configure Trading Caps** via Settings page
3. **Set up Notifications** (Discord/WhatsApp/Email)
4. **Test Paper Trading** with 
5. **Enable Auto-Payout** (optional)