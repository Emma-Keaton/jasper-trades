# Deploying Kronos Service to Render

This document explains how to deploy the Kronos prediction service as a separate Render web service.

## Overview

The Kronos service provides time-series forecasting predictions using multiple model variants:
- **kronos-mini**: Fast inference, 2048 context window
- **kronos-small**: Balanced accuracy/speed, 512 context window
- **kronos-base**: Highest accuracy (not yet available on HF)

## Architecture

```
┌─────────────────────────────────────────┐
│ Main Backend (Render)                   │
│ https://jasper-trades.onrender.com      │
│ - FastAPI trading platform              │
│ - Calls Kronos service via HTTP         │
│ - Handles broker integration            │
└─────────────────────────────────────────┘
                  │
                  │ HTTP POST /predict
                  ▼
┌─────────────────────────────────────────┐
│ Kronos Service (Render - NEW)           │
│ https://jasper-trades-kronos.onrender   │
│ - Time-series prediction API            │
│ - CPU-only inference                    │
│ - Multiple model strategies             │
└─────────────────────────────────────────┘
```

## Step 1: Create Git Branch for Kronos Service

```bash
# Create new branch for Kronos service deployment
git checkout -b deploy-kronos-service

# Add all Kronos service files
git add backend/kronos-service/
git commit -m "feat: Add Kronos prediction service for Render deployment"
```

## Step 2: Deploy to Render

### 2.1 Create New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository

### 2.2 Configure Service

| Setting | Value |
|---------|-------|
| **Name** | `jasper-trades-kronos` |
| **Environment** | `Python 3.11` |
| **Build Command** | `pip install -r backend/kronos-service/requirements.txt` |
| **Start Command** | `uvicorn backend.kronos-service.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` (512MB RAM) |
| **Region** | Same as main backend |
| **Branch** | `deploy-kronos-service` (or main) |
| **Root Directory** | Leave blank (repo root) |

### 2.3 Environment Variables

Add these in Render dashboard → Environment:

```
LOG_LEVEL=INFO
MODEL_UNLOAD_TIMEOUT=300
PORT=8080
```

### 2.4 Advanced Settings

- **Auto-Deploy**: Enable (pushes deploy automatically)
- **Health Check Path**: `/health`
- **Docker**: No (use Python runtime)

## Step 3: Update Main Backend Configuration

After Kronos service is deployed and returns a URL (e.g., `https://jasper-trades-kronos.onrender.com`):

1. Go to **main backend** Render dashboard
2. Navigate to **Environment** tab
3. Add environment variable:

```
KRONOS_SERVICE_URL=https://jasper-trades-kronos.onrender.com
```

4. Save and redeploy main backend

## Step 4: Verify Deployment

### 4.1 Test Kronos Service Directly

```bash
# Health check
curl https://jasper-trades-kronos.onrender.com/health

# Test prediction
curl https://jasper-trades-kronos.onrender.com/predict/AAPL

# Test with strategy
curl "https://jasper-trades-kronos.onrender.com/predict/AAPL?strategy=ensemble"

# Batch predictions
curl -X POST https://jasper-trades-kronos.onrender.com/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "NVDA"], "strategy": "cascade"}'
```

### 4.2 Test Main Backend Integration

```bash
# Check system status
curl https://jasper-trades.onrender.com/api/v1/status

# Check Kronos stats
curl https://jasper-trades.onrender.com/api/v1/kronos/stats
```

Expected response:
```json
{
  "service_type": "remote",
  "url": "https://jasper-trades-kronos.onrender.com",
  "status": "healthy",
  "models_loaded": [],
  "device": "cpu"
}
```

## API Endpoints

### Prediction Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict/{symbol}` | GET | Single symbol prediction |
| `/predict/batch` | POST | Multiple symbols |
| `/test` | GET | Test endpoint (AAPL) |
| `/health` | GET | Health check |
| `/strategies` | GET | Available strategies |

### Parameters

#### GET `/predict/{symbol}`
- `symbol` (path): Stock ticker (e.g., "AAPL")
- `strategy` (query): "cascade", "ensemble", "mini", "small", "base"
- `lookback_days` (query): Number of historical days (default: 30)

#### POST `/predict/batch`
```json
{
  "symbols": ["AAPL", "TSLA", "NVDA"],
  "strategy": "cascade",
  "lookback_days": 30
}
```

### Response Format

```json
{
  "symbol": "AAPL",
  "direction": "UP",
  "confidence": 0.72,
  "predicted_change": 0.0072,
  "strategy": "cascade_cpu",
  "timestamp": "2026-06-30T12:00:00Z",
  "inference_time_ms": 3500.0
}
```

## Prediction Strategies

| Strategy | Description | Speed | Use Case |
|----------|-------------|-------|----------|
| `cascade` | Sequential filtering (mini → small) | ⚡⚡ | Screening pairs |
| `ensemble` | Weighted average (mini + small) | ⚡ | Robustness |
| `mini` | Kronos-mini only | ⚡⚡⚡ | Fast inference |
| `small` | Kronos-small only | ⚡⚡ | Balanced |
| `base` | Kronos-base only | ⚡ | Highest accuracy |

## Monitoring

### Check Service Logs

```bash
# Go to Render dashboard → jasper-trades-kronos → Logs
```

### Key Indicators

- ✅ "Loading model: kronos-mini" - model loading
- ✅ "Successfully loaded" - inference ready
- ⚠️ "Unloading previous model" - memory management
- ❌ "Model loading failed" - deployment issue

## Troubleshooting

### Issue: Service returns 500 error

**Cause**: Model failed to download or load

**Solution**:
1. Check Render logs for error messages
2. Verify HuggingFace model exists
3. Add fallback model handling (already in code)

### Issue: Service sleeps after 15 minutes

**Cause**: Render free tier auto-sleeps

**Solution**:
- Upgrade to Hobby tier ($7/month) for always-on
- Or accept cold-start latency (~15 seconds for model load)

### Issue: Out of Memory (OOM) errors

**Cause**: Model exceeds 512MB RAM

**Solution**:
1. Use `kronos-mini` only (smallest model)
2. Reduce batch size in requests
3. Set `MODEL_UNLOAD_TIMEOUT=60` (unload after 1 minute)

## Cost

- **Free Tier**: $0/month (512MB RAM, auto-sleeps)
- **Hobby Tier**: $7/month (1GB RAM, always-on)
- **Pro Tier**: $15/month (2GB RAM, always-on)

Recommendation: Start with **Free tier** for testing, upgrade to **Hobby** for production.

## Scaling

### Vertical Scaling
- Upgrade Render instance type (free → hobby → pro)

### Horizontal Scaling
- Render free tier doesn't support multiple instances
- Upgrade to Hobby+ for load balancing

## Future Improvements

1. **Model optimization**: Quantize models to int8 for faster loading
2. **Preloading**: Keep models loaded during business hours
3. **Caching**: Cache predictions for frequently requested symbols
4. **GPU acceleration**: Upgrade to GPU-enabled instances (if available)
5. **Model versioning**: Version models for A/B testing

## Migration from Colab

This service **replaces** the Google Colab notebook approach:

| Feature | Colab | Render Service |
|---------|-------|----------------|
| Uptime | 12-hour sessions | 24/7 |
| GPU | Yes (free) | CPU only |
| Reliability | Session timeouts | Always available |
| Cost | Free (limited) | Free (unlimited) |
| Setup | Manual notebook | Auto-deploy |

To migrate:
1. Set `KRONOS_SERVICE_URL` in main backend (this document)
2. Remove `KRONOS_COLAB_URL` from configuration
3. Update any frontend references to use new URL