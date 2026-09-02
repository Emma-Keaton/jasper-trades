---
name: kronos-remote-service-deployment
description: Deploy Kronos time-series forecasting as separate Render microservice with HTTP client integration
source: auto-skill
extracted_at: '2026-06-30T12:00:00.000Z'
---

# Kronos Remote Service Deployment

Replace Colab/local Kronos with a separate Render-deployed microservice for 24/7 uptime and simplified architecture.

## Architecture

```
Main Backend (Render) ──HTTP POST──> Kronos Service (Render)
https://jasper-trades.onrender.com   https://jasper-trades-kronos.onrender.com
- FastAPI trading platform           - Time-series prediction API
- Calls Kronos via HTTP client       - CPU-only inference (512MB RAM)
- Handles broker integration         - Multiple model strategies
```

## Implementation Steps

### 1. Create Kronos Microservice Directory

```bash
mkdir backend/kronos-service
```

### 2. Create Service Files

**requirements.txt**:
```
torch>=2.0.0
transformers>=4.35.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.4.0
pandas>=2.1.0
numpy>=1.24.0
scikit-learn>=1.3.0
yfinance>=0.2.28
httpx>=0.25.0
python-dotenv>=1.0.0
safetensors>=0.4.0
```

**main.py**:
- FastAPI server with prediction endpoints
- LSTM/Transformer models (lightweight, CPU-optimized)
- Lazy model loading (unload after timeout to save memory)
- Multiple strategies: cascade, ensemble, single-model

Key endpoints:
- `GET /predict/{symbol}?strategy=cascade`
- `POST /predict/batch` (JSON body: `{"symbols": [...], "strategy": "cascade"}`)
- `GET /health`
- `GET /strategies`

### 3. Create Remote Client in Main Backend

**backend/app/services/kronos_remote.py**:

```python
class KronosRemoteClient:
    def __init__(self):
        self.base_url = settings.KRONOS_SERVICE_URL
    
    async def predict(self, symbol: str, strategy: str = "cascade", lookback_days: int = 30):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/predict/{symbol}",
                params={"strategy": strategy, "lookback_days": lookback_days}
            )
            return response.json()
    
    async def predict_batch(self, symbols: List[str], strategy: str = "cascade"):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/predict/batch",
                json={"symbols": symbols, "strategy": strategy}
            )
            return response.json()
```

### 4. Update Configuration

**backend/app/config.py** - Add:
```python
KRONOS_SERVICE_URL: Optional[str] = None  # Remote Kronos service URL
```

**backend/.env.render** - Add:
```
KRONOS_SERVICE_URL="https://jasper-trades-kronos.onrender.com"
```

### 5. Update System Endpoints

**backend/app/api/v1/system.py** - Modify `/kronos/stats`:
- Check if `KRONOS_SERVICE_URL` is configured
- Call remote health check endpoint
- Return `service_type: "remote"` with URL and health status

### 6. Deploy to Render

**Create new web service**:
- Name: `jasper-trades-kronos`
- Build Command: `pip install -r backend/kronos-service/requirements.txt`
- Start Command: `uvicorn backend.kronos-service.main:app --host 0.0.0.0 --port $PORT`
- Instance Type: Free (512MB RAM)
- Health Check Path: `/health`

**Environment Variables**:
```
LOG_LEVEL=INFO
MODEL_UNLOAD_TIMEOUT=300
PORT=8080
```

### 7. Configure Main Backend

After Kronos service deploys:
1. Set `KRONOS_SERVICE_URL` in main backend environment
2. Redeploy main backend
3. Verify via `/api/v1/kronos/stats` endpoint

## Trading Style Impact

- **No local model loading** = zero RAM pressure on main backend
- **CPU-only inference** = 5-10 second latency (acceptable for swing trading)
- **Free tier** = unlimited uptime (unlike Colab's 12-hour sessions)
- **Separate deployment** = independent scaling and updates

## Kronos Service URL

Use `KRONOS_SERVICE_URL` to point to the remote Kronos deployment:

| Config | Description |
|--------|-------------|
| `KRONOS_SERVICE_URL` | Remote Kronos service URL (Render) |

## Prediction Strategies

- **cascade**: Sequential filtering (mini → small) - fastest for screening
- **ensemble**: Weighted average (mini + small) - most robust
- **mini/small/base**: Single model - fine-tuned control

## Testing

```bash
# Test Kronos service directly
curl https://jasper-trades-kronos.onrender.com/health
curl https://jasper-trades-kronos.onrender.com/predict/AAPL?strategy=cascade

# Test from main backend
curl https://jasper-trades.onrender.com/api/v1/kronos/stats
```

Expected response includes:
```json
{
  "service_type": "remote",
  "url": "https://jasper-trades-kronos.onrender.com",
  "status": "healthy",
  "device": "cpu"
}
```