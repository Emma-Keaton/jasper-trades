---
name: render-deployment-configuration
description: Complete Render.com deployment setup for Jasper Trades monorepo with frontend, backend, and OpenWA
source: auto-skill
extracted_at: '2026-06-09T16:23:21.557Z'
---

# Render Deployment Configuration - Jasper Trades

## Overview

Jasper Trades deploys as a **monorepo** to Render.com, serving both the Next.js frontend and FastAPI backend from a single service. This configuration includes WhatsApp notifications via OpenWA.

## Prerequisites

- GitHub repository with the Jasper Trades codebase
- Render.com account (free tier: 512MB RAM, 500 hours/month)
- NVIDIA NIM API key from https://build.nvidia.com/

## Render Configuration

### Service Type
**Web Service** (Python runtime)

### Root Directory
`.` (repository root, NOT `backend` subfolder)

### Build Command
```bash
pip install -r backend/requirements.txt && cd frontend && npm ci && NEXT_TELEMETRY_DISABLED=1 npm run build && cd .. && mkdir -p backend/static && cp -r frontend/out/* backend/static/ && npm install -g @open-wa/wa-automate
```

**What this does:**
1. Installs Python dependencies (FastAPI, pydantic, email-validator, etc.)
2. Installs Node.js dependencies for frontend
3. Builds Next.js with static export (`output: 'export'` in next.config.js)
4. Copies static files from `frontend/out/` to `backend/static/`
5. Installs OpenWA globally for WhatsApp notifications

### Start Command
```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Why `cd backend`:** Python needs to run from the backend directory to find the `app` module.

### Health Check Path
```
/api/v1/health
```

## Key Configuration Files

### 1. `next.config.js` (Frontend)
```javascript
module.exports = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  output: 'export',           // Static HTML export
  images: {
    unoptimized: true,        // Required for static export
  },
};
```

### 2. `backend/app/main.py` (Frontend Serving)
```python
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists() and (static_dir / "index.html").exists():
    # Serve Next.js static assets
    app.mount("/_next/static", StaticFiles(directory=str(static_dir / "_next" / "static")))
    # Catch-all route serves index.html for SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(static_dir / "index.html")
```

### 3. `Dockerfile` (Optional - for Docker deployments)
Includes Node.js, Chromium dependencies, and OpenWA for WhatsApp support.

## Environment Variables

**Required:**
```env
# Python/Runtime
PYTHON_VERSION=3.11.0
PORT=10000

# Security (generate random strings)
SECRET_KEY=<32+ random characters>
API_AUTH_KEY=<random auth token>

# NVIDIA NIM API (required for AI features)
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# Model Routing (FREE tier)
MODEL_FAST="nvidia/nemotron-mini-4b-instruct"
MODEL_BALANCED="moonshotai/kimi-k2.6"
MODEL_SMART="nvidia/nemotron-3-ultra-550b-a55b"
MODEL_DEEP="nvidia/nemotron-3-ultra-550b-a55b"

# Database
DATABASE_URL="sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"
DATA_DIR="./data

# CORS (add your production domain)
CORS_ORIGINS="http://localhost:3000,https://your-domain.com"
```

**Optional (configure via Settings page after deployment):**
```env
BINANCE_API_KEY=
BINANCE_API_SECRET=
KRONOS_COLAB_URL=
KRONOS_COLAB_STRATEGY="cascade"
```

## Critical Dependencies

**`backend/requirements.txt` must include:**
```
pydantic>=2.10.0
email-validator>=2.2.0        # Required by pydantic EmailStr
...
```

**Common Error:** `ModuleNotFoundError: No module named 'email_validator'`
**Fix:** Add to requirements.txt and redeploy

## Frontend Build Issues

**Problem:** Frontend not served (API-only mode)
**Cause:** Static files not copied or wrong path

**Solution:**
1. Ensure `next.config.js` has `output: 'export'`
2. Build command copies from `frontend/out/` (not `.next/`)
3. Backend looks for `backend/static/index.html`

**Verify locally:**
```bash
cd frontend && npm run build
ls -la out/  # Should have index.html, _next/, public/
```

## OpenWA/WhatsApp Setup

**Build command includes:**
```bash
npm install -g @open-wa/wa-automate
```

**System dependencies (Dockerfile):**
```dockerfile
RUN apt-get install -y chromium libnss3 libatk-bridge2.0-0 libdrm2 ...
```

**Backend initialization:**
```python
# app/main.py
from app.services.embedded_openwa import embedded_openwa
await embedded_openwa.start()
```

**Note:** WhatsApp requires browser automation (Chromium). On Render free tier, this may be resource-intensive. Consider disabling if not needed.

## Preventing Sleep (Free Tier)

Render free tier sleeps after 15 minutes of inactivity.

**Solution:** Use UptimeRobot
1. Create account at https://uptimerobot.com/
2. Add HTTP monitor: `https://your-app.onrender.com/api/v1/health`
3. Check interval: 5 minutes
4. Backend stays awake 24/7

## Deployment Checklist

- [ ] `next.config.js` has `output: 'export'`
- [ ] `backend/requirements.txt` includes `email-validator`
- [ ] Build command copies `frontend/out/*` to `backend/static/`
- [ ] Start command uses `cd backend && ...`
- [ ] `SECRET_KEY` and `API_AUTH_KEY` generated (32+ chars)
- [ ] NVIDIA API key configured
- [ ] CORS_ORIGINS includes production domain
- [ ] UptimeRobot monitor configured (free tier)

## Post-Deployment Configuration

After deployment, configure via Settings page (`https://your-app.onrender.com/settings`):

1. **NVIDIA NIM API** - Paste API key, test connection
3. **Notifications** - Configure Discord/WhatsApp/Email (optional)
4. **Kronos Colab** - Add Colab URL for AI predictions (optional)

## Troubleshooting

### "ModuleNotFoundError: email_validator"
- Add `email-validator>=2.2.0` to `backend/requirements.txt`
- Redeploy (forces `pip install -r requirements.txt`)

### "Frontend not built" / API-only mode
- Check build logs for `npm run build` success
- Verify `frontend/out/index.html` exists after build
- Ensure build command copies to `backend/static/`

### "Cannot find module 'app'"
- Start command must include `cd backend &&`
- Or set `PYTHONPATH=/opt/render/project/src/backend`

### OpenWA fails to start
- Missing Chromium dependencies
- Install: `npm install -g @open-wa/wa-automate`
- Or disable WhatsApp if not needed

## Cost Estimation

**Render Free Tier:**
- 500 hours/month (~20 days)
- 512MB RAM
- $0/month

**With UptimeRobot:**
- Stays awake 24/7
- Still $0/month (Render doesn't charge for idle time, just active hours)

**Upgrade Option:**
- Render Standard: $7/month (unlimited hours, 1GB RAM)
- Recommended for production use

## Architecture Summary

```
Render Web Service (Python 3.11)
├── Backend (FastAPI on port $PORT)
│   ├── API routes: /api/v1/*
│   ├── Static files: / (from backend/static/)
│   └── OpenWA: Embedded Node.js process
├── Frontend (Next.js static export)
│   ├── index.html
│   ├── _next/static/
│   └── public/
└── Database
    └── SQLite (file-based in ./data/)
```

**Single deployment, single URL, full-stack application.**