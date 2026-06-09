---
name: render-monorepo-deployment
description: Deploy full-stack Next.js + FastAPI app to Render using Python runtime with unified build
source: auto-skill
extracted_at: '2026-06-09T18:30:00.000Z'
---

# Render Monorepo Deployment - Backend + Frontend Unified

This skill covers deploying a full-stack application (Next.js frontend + FastAPI backend) to Render using the **Python runtime** with a unified build process.

## Architecture

- **Backend**: FastAPI (Python 3.11)
- **Frontend**: Next.js 15 (React 19, TypeScript)
- **Deployment**: Single Render web service serving both API and static frontend files
- **Cost**: Free tier (512MB RAM, 500 hours/month)

## Render Configuration

### Platform Settings

**Runtime:** Python 3

**Root Directory:** `.` (repo root, NOT a subfolder)

**Build Command:**
```bash
pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build && cd .. && mkdir -p backend/static && cp -r frontend/.next/static backend/static/ 2>/dev/null || true && cp -r frontend/public backend/static/ 2>/dev/null || true
```

**Start Command:**
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

**Health Check Path:** `/api/v1/health`

### Why This Works

1. **Build Phase**:
   - Installs Python dependencies from `backend/requirements.txt`
   - Installs Node.js dependencies in `frontend/`
   - Builds Next.js production bundle
   - Copies static assets to `backend/static/` for serving

2. **Runtime**:
   - FastAPI starts on port `$PORT` (Render-provided)
   - Backend code in `backend/app/main.py` detects `backend/static/.next` and serves frontend
   - API routes at `/api/v1/*`, frontend at `/`

## Backend Changes Required

Add static file serving to FastAPI `main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

static_dir = Path(__file__).parent.parent / "static"

if static_dir.exists() and (static_dir / ".next").exists():
    # Mount Next.js static assets
    app.mount("/_next/static", StaticFiles(directory=str(static_dir / ".next" / "static")), name="next_static")
    
    # Catch-all route for SPA routing
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs"):
            raise HTTPException(status_code=404)
        
        index_file = static_dir / ".next" / "standalone" / "public" / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        
        return HTMLResponse("Frontend not built", status_code=404)
```

## Environment Variables

Essential variables for Render dashboard:

```env
PYTHON_VERSION=3.11.0
PORT=10000
DEBUG=false

DATABASE_URL="sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"
DATA_DIR="./data"

SECRET_KEY="<generate 32+ char random string>"
API_AUTH_KEY="<generate random string>"

NVIDIA_API_KEY="<your NVIDIA NIM API key>"
NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"

MODEL_FAST="nvidia/nemotron-mini-4b-instruct"
MODEL_SMART="nvidia/nemotron-3-ultra-550b-a55b"

CORS_ORIGINS="https://your-domain.com"
```

**Generate secrets:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Preventing Free Tier Sleep

Render free tier sleeps after 15 minutes of inactivity. Use UptimeRobot:

1. Go to https://uptimerobot.com/
2. Create free account
3. Add HTTP monitor: `https://your-app.onrender.com/api/v1/health`
4. Check interval: 5 minutes
5. Backend stays awake 24/7

## Troubleshooting

### Build Fails with "Module Not Found"

- Ensure `npm ci` runs before `npm run build`
- Check `frontend/package-lock.json` exists (commit it)
- Verify Node.js version compatibility (use Node 20.x)

### Frontend Returns 404 After Deploy

- Check `backend/static/.next` directory exists in build logs
- Verify static files were copied: `cp -r frontend/.next/static backend/static/`
- Ensure FastAPI static mounting code is in `main.py`

### CORS Errors from Frontend

- Update `CORS_ORIGINS` env var with your Render URL
- Format: `https://your-app.onrender.com` (no trailing slash)
- Multiple origins: comma-separated

### Build Timeout (15 min limit)

- Use `npm ci` instead of `npm install` (faster, deterministic)
- Disable Next.js telemetry: `NEXT_TELEMETRY_DISABLED=1 npm run build`
- Consider upgrading to Render paid ($7/month, no timeout)

## Cost Estimation

| Service | Free Tier | Paid Option |
|---------|-----------|-------------|
| Render Web Service | 500 hrs/month | $7/month (unlimited) |
| UptimeRobot | 5 min checks | $6.50/month (1 min) |
| NVIDIA NIM API | $25 credits/month | Pay-as-you-go |
| **Total** | **$0/month** | **$7-15/month** |

## Alternative: Separate Deployments

For better scalability:

- **Frontend**: Deploy to Vercel (optimized for Next.js)
- **Backend**: Deploy to Render (Python/FastAPI)
- Update `NEXT_PUBLIC_API_URL` in Vercel env vars

This approach gives:
- Faster frontend (Vercel edge network)
- No build timeout issues
- Independent scaling
- Still free tier for both