---
name: render-deployment-troubleshooting
description: Step-by-step troubleshooting for Render.com deployment issues including missing dependencies, route conflicts, and environment configuration
source: auto-skill
extracted_at: '2026-06-13T17:23:00.037Z'
---

# Render Deployment Troubleshooting

This skill covers systematic approaches to diagnosing and fixing common Render.com deployment failures for Python/FastAPI + Next.js applications.

## Common Issues & Solutions

### 1. Missing Python Dependencies

**Symptom:** `ModuleNotFoundError: No module named 'xyz'`

**Solution:**
```bash
# Add missing package to requirements.txt
echo "package-name>=version" >> backend/requirements.txt
git add backend/requirements.txt
git commit -m "Fix: Add package-name for xyz module"
git push origin main
```

**Common missing packages:**
- `pytz>=2024.2` - Timezone support
- `cryptography>=41.0.0` - Token encryption

### 2. Frontend Build Output Directory Issues

**Symptom:** `cp: cannot stat '/app/frontend/out/*': No such file or directory`

**Root Cause:** Next.js 15+ doesn't output to `out/` folder by default without `output: 'export'` config.

**Solution for Split Deployment (Vercel + Render):**

Update `Dockerfile` to skip frontend build:
```dockerfile
# Remove these lines:
# RUN cd frontend && npm ci
# RUN cd frontend && npm run build
# RUN cp -r /app/frontend/out/* /app/backend/static/

# Add placeholder instead:
RUN mkdir -p /app/backend/static && \
    echo "Backend-only mode - frontend served on Vercel" > /app/backend/static/index.html
```

Update `render-build.sh`:
```bash
#!/bin/sh
# Backend-only build
pip install -r backend/requirements.txt
mkdir -p backend/static
echo "Backend-only mode" > backend/static/index.html
```

**Why:** Frontend deployed separately on Vercel, backend on Render serves API only.

### 3. Environment Variable Validation on Startup

**Symptom:** `ValueError: Missing configuration` on app startup

**Root Cause:** Services validate env vars at module load time, crashing before server starts.

**Solution - Make validation lazy:**

```python
# ❌ BAD - crashes on import
class MyService:
    def __init__(self):
        if not os.getenv("API_KEY"):
            raise ValueError("Missing API_KEY")  # Crashes app!

# ✅ GOOD - graceful initialization
class MyService:
    def __init__(self):
        self._is_configured = bool(os.getenv("API_KEY"))
    
    def _ensure_configured(self):
        if not self._is_configured:
            raise ValueError("Not configured - set API_KEY env var")
    
    def do_something(self):
        self._ensure_configured()  # Only validate when actually used
```

**Benefits:**
- App starts successfully even without optional features configured
- Users can configure features later via Settings page
- Only fails when feature is actually accessed

### 4. npm ci Failing Due to Lock File Sync

**Symptom:** 
```
npm error `npm ci` can only install packages when package.json and package-lock.json are in sync
npm error Missing: some-package@1.0.0 from lock file
```

**Solution:**
```bash
cd frontend
npm install --package-lock-only  # Regenerates lock file without installing
git add package-lock.json
git commit -m "Fix: Sync package-lock.json"
git push origin main
```

**Why:** `npm ci` requires exact sync between package.json and package-lock.json.

### 5. Invalid requirements.txt Entry

**Symptom:** 
```
ERROR: Invalid requirement: -py>=0.25.0
pip: error: no such option: -p
```

**Root Cause:** Missing package name (e.g., `-py` should be `alpaca-py` or remove entirely)

**Solution:**
```bash
# Edit requirements.txt - fix or remove broken line
# From:
-py>=0.25.0

# To:
alpaca-py>=0.25.0
# OR remove entirely if not needed
```

### 6. Route Prefix Conflicts

**Symptom:** 404 errors on endpoints that exist in code

**Root Cause:** Double prefixing when both router file AND main.py add same prefix

**Solution:**
```python
# ✅ In router file (e.g., broker_connections.py)
router = APIRouter(prefix="/brokers", tags=["brokers"])

# ✅ In main.py
app.include_router(broker_connections.router, prefix="/api/v1", tags=["brokers"])
# Final route: /api/v1/brokers/*

# ❌ DON'T do this:
# Router: prefix="/api/v1/brokers"
# Main: prefix="/api/v1"
# Result: /api/v1/api/v1/brokers (404)
```

### 7. Port Binding Issues

**Symptom:** `Uvicorn running on http://0.0.0.0:8000` but Render shows "No open ports detected"

**Root Cause:** Render expects PORT from environment, hardcoded value ignored

**Solution:**
```python
# main.py
from app.config import settings

# Use PORT env var from Render
port = int(os.getenv("PORT", 8080))
uvicorn.run(app, host="0.0.0.0", port=port)
```

**.env.render:**
```bash
PORT=8080  # Must match what Dockerfile EXPOSEs
```

## Deployment Checklist

Before deploying to Render:

### Backend (requirements.txt)
- [ ] All imports have corresponding packages
- [ ] No broken entries (missing package names)
- [ ] Versions are compatible with target Python version

### Docker Configuration
- [ ] Dockerfile skips frontend build if using split deployment
- [ ] Static folder created (even if empty)
- [ ] PORT env var respected (not hardcoded)
- [ ] Data directories created (`/app/backend/data/*`)

### Environment Variables
- [ ] All required vars in `.env.render`
- [ ] Optional services have graceful degradation
- [ ] Encryption keys generated (not empty strings)

### Code Quality
- [ ] Service initialization doesn't crash on missing optional config
- [ ] Routes use consistent prefix pattern
- [ ] No module-level validation that raises exceptions
- [ ] All imports can resolve without env vars

## Typical Deployment Flow

1. **Prep repo:**
   ```bash
   git pull origin main
   npm install --package-lock-only  # Ensure lock file sync
   git add package-lock.json
   ```

2. **Push to GitHub:**
   ```bash
   git commit -m "Ready for Render deploy"
   git push origin main
   ```

3. **Render auto-deploys** from GitHub

4. **Monitor logs** for errors

5. **Fix issues** using patterns above, push again

6. **Verify deployment:**
   ```bash
   curl https://your-backend.onrender.com/api/v1/health
   # Expected: {"status":"healthy",...}
   ```

## When Things Still Fail

1. **Check Render logs** - Most errors show exact line number
2. **Test locally** with same environment:
   ```bash
   docker build -t jasper-test .
   docker run -p 8080:8080 --env-file backend/.env.render jasper-test
   ```
3. **Simplify** - Remove optional features temporarily
4. **Check Python version** - Some packages require specific versions
5. **Verify file paths** - Linux is case-sensitive (`app/Main.py` ≠ `app/main.py`)

## Key Takeaways

- **Lazy validation** - Don't crash on startup for optional features
- **Split deployment** - Frontend on Vercel, backend on Render (simpler than monorepo)
- **Lock file sync** - Always regenerate before deploy
- **Environment variables** - Use `os.getenv()` with defaults, validate on use not import
- **Route organization** - Prefix once, not twice