# Jasper Kronos — Forecast Service

Local + cloud Kronos K-line foundation model service for the Jasper Trades
trading platform. Runs on a **2GB RAM laptop** using `Kronos-mini` (4.1M params,
~16 MB weights) from Hugging Face, and deploys to **Modal cloud** for
multi-device access.

```
trading app ──▶ backend ──▶ kronos service ──▶ Kronos-mini (CPU)
   (Next.js)     (FastAPI)   (localhost:8001 or Modal)  (Hugging Face)
```

## Layout

```
kronos/
  kronos_service/   Python service: engine, client, marketdata, limits, gate
  kronos_lib/       Vendored Kronos library (from shiyu-coder/Kronos, MIT)
  modal_app.py      Modal cloud deployment
  start_kronos.py   Local service launcher (http://localhost:8001)
  launch_kronos.py  Unified launcher: --local | --cloud
  requirements.txt  Python dependencies (CPU-only torch)
  .env.example      Environment configuration template
```

## Model Choice: Kronos-mini (fits 2GB RAM)

| Variant | Params | Weights | Context | RAM Fit | Speed |
|---------|--------|---------|---------|---------|-------|
| `Kronos-mini` | 4.1M | ~16 MB | 2048 | ✅ 2GB laptop | Fast (~1s per forecast) |
| `Kronos-small` | 24.7M | ~100 MB | 512 | ⚠️ Tight on 2GB | ~4x slower |

`Kronos-mini` is the default and recommended for a 2GB RAM laptop.

## Quick Start

### 1. Install dependencies

```powershell
cd E:\Projects\jasper-trades\kronos
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 2. Configure environment

```powershell
copy .env.example .env
# Edit .env: set KRONOS_API_KEY to a random secret
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Run locally

```powershell
python launch_kronos.py --local
# Service starts at http://localhost:8001
# First launch downloads Kronos-mini from Hugging Face (~1–3 min)
```

### 4. Connect the backend

Add to `E:\Projects\jasper-trades\backend\.env`:

```
KRONOS_SERVICE_URL=http://localhost:8001
KRONOS_API_KEY=<same-secret-as-kronos-env>
```

Then restart the backend:
```powershell
cd E:\Projects\jasper-trades\backend
python start_server.py
```

The backend's `kronos_remote.py` client will connect to the local Kronos
service at `http://localhost:8001` for predictions.

### 5. Connect the frontend

The frontend already connects to the backend via `NEXT_PUBLIC_API_URL`.
No additional frontend config is needed — predictions flow through the
backend's `/api/v1/kronos/*` endpoints.

## Cloud Deployment (Modal)

```powershell
# Authenticate with Modal (one-time)
modal token set

# Deploy
python launch_kronos.py --cloud

# Modal prints a URL like:
# https://jasper-kronos--web-xxx.modal.run
```

Add to `backend/.env` for cloud:

```
KRONOS_SERVICE_URL=https://jasper-kronos--web-xxx.modal.run
KRONOS_API_KEY=<same-secret>
```

The same `.env` works for both local and cloud — just change
`KRONOS_SERVICE_URL`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health + model status |
| `/forecast` | POST | Forecast from OHLCV candles |
| `/forecast/closes` | POST | Forecast from close-only prices |
| `/forecast/batch` | POST | Batch forecast for multiple symbols |

Client example:

```python
import httpx
response = httpx.post(
    "http://localhost:8001/forecast/closes",
    headers={"X-API-Key": "<secret>"},
    json={"closes": [100, 101, 99, ...], "horizon": 24, "samples": 10},
)
```

## Backend Integration

The jasper-trades backend (`backend/app/services/kronos_remote.py`) already
implements a `KronosRemoteClient` that:

1. Fetches market data (OHLCV) from data connectors
2. Posts to the Kronos service `/forecast/closes` endpoint
3. Records predictions for calibration against realised prices
4. Falls back to a local tiered forecaster when Kronos is unavailable

Set `KRONOS_SERVICE_URL` and `KRONOS_API_KEY` in `backend/.env` to enable it.

## Memory Notes (2GB RAM)

- Model weights (~16 MB) are loaded on first forecast and cached by Hugging Face
- Torch is CPU-only with 2 threads to limit RAM usage
- No GPU is used (GPU would consume the monthly Modal credit on a free tier)
- For cloud, the container is sized at 1 GB RAM and scales to zero