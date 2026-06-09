---
name: kronos-colab-3model-integration
description: Integrate Google Colab GPU hosting for Kronos 3-model ensemble predictions with cascade/ensemble/context strategies
source: auto-skill
extracted_at: '2026-06-08T21:36:37.142Z'
---

# Kronos Colab 3-Model Integration

## Overview

Integrate Google Colab's free GPU to run three Kronos models (mini/small/base) concurrently for enhanced time-series forecasting. This approach provides:

- **Cascade strategy**: Fast filtering (mini→small→base) for screening hundreds of pairs
- **Ensemble strategy**: Weighted average (20/30/50) for maximum accuracy
- **Context strategy**: Auto-select model by data length (long→mini, short→base)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Backend (Local/Cloud)                                   │
│ - Config: KRONOS_COLAB_URL, KRONOS_COLAB_STRATEGY      │
│ - Converts OHLCV → returns format                       │
│ - Calls Colab /predict/batch endpoint                   │
└─────────────────────────────────────────────────────────┘
                          │
                          │ HTTP POST with returns array
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Colab Notebook (kronos_colab.ipynb)                     │
│ - 3 models loaded: mini + small + base                  │
│ - 2 tokenizers: base (512 ctx) + 2k (2048 ctx)         │
│ - Strategy router selects model(s)                      │
│ - Returns: {direction, predicted_change, strategy}      │
└─────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Backend Configuration (`backend/app/config.py`)

Add Colab-specific settings:

```python
# Kronos Colab Integration (3-model ensemble)
KRONOS_COLAB_URL: Optional[str] = None  # Colab public URL (ngrok)
KRONOS_COLAB_STRATEGY: str = "cascade"  # cascade|ensemble|context|mini|small|base
```

### 2. Hybrid Service Update (`backend/app/services/kronos/hybrid_service.py`)

Update `_colab_predict()` to:

```python
async def _colab_predict(
    self,
    symbol: str,
    ohlcv_data: List[List[float]],
    forecast_horizon: int,
) -> Dict[str, Any]:
    # Convert OHLCV to returns (Kronos input format)
    close_prices = [bar[3] for bar in ohlcv_data]
    returns = [(close_prices[i] - close_prices[i-1]) / close_prices[i-1] 
               for i in range(1, len(close_prices))]

    # Call Colab batch API with strategy
    response = await client.post(
        f"{self.colab_url}/predict/batch",
        json={
            "symbols": [symbol],
            "strategy": settings.KRONOS_COLAB_STRATEGY,
            "returns": returns,
            "forecast_horizon": forecast_horizon,
        },
        timeout=60.0,
    )
    
    # Parse and convert Colab response to backend format
    symbol_result = result[symbol]
    predicted_return = (abs(symbol_result["predicted_change"]) 
                        if symbol_result["direction"] == "UP" 
                        else -abs(symbol_result["predicted_change"]))
    
    # Generate price predictions from returns
    last_close = ohlcv_data[-1][3]
    predictions = [last_close * (1 + predicted_return * (i + 1) / forecast_horizon) 
                  for i in range(forecast_horizon)]
```

**Key transformations:**
- OHLCV → returns conversion (close price changes)
- Returns → price predictions (reverse transformation)
- Direction string → signed float for `predicted_return`

### 3. Colab Notebook (`kronos_colab.ipynb`)

**Cell 1 - Install dependencies:**
```python
!pip install torch transformers accelerate fastapi uvicorn nest-asyncio yfinance pandas numpy git+https://github.com/amazon-science/chronos-forecasting.git
```

**Cell 2 - Load all 3 models:**
```python
from model import Kronos, KronosTokenizer, KronosPredictor

# Load tokenizers
tokenizer_base = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
tokenizer_2k = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-2k")

# Load models
model_mini = Kronos.from_pretrained("NeoQuasar/Kronos-mini")
model_small = Kronos.from_pretrained("NeoQuasar/Kronos-small")
model_base = Kronos.from_pretrained("NeoQuasar/Kronos-base")

# Create predictors
predictor_mini = KronosPredictor(model_mini, tokenizer_2k, device=device, max_context=2048)
predictor_small = KronosPredictor(model_small, tokenizer_base, device=device, max_context=512)
predictor_base = KronosPredictor(model_base, tokenizer_base, device=device, max_context=512)
```

**Cell 3 - Implement strategies:**

- `predict_cascade()`: Run mini first, filter weak signals, escalate to small then base
- `predict_context_routed()`: Use mini if len(data) > 512, else base
- `predict_ensemble()`: Weighted average with weights (0.2, 0.3, 0.5)

**Cell 4 - API server with strategy routing:**
```python
@app.get("/predict/{symbol}")
async def predict(symbol: str, strategy: str = "cascade"):
    return predict_direction(symbol, strategy=strategy)

@app.post("/predict/batch")
async def predict_batch_endpoint(request: BatchRequest):
    return predict_batch(request.symbols, strategy=request.strategy)
```

**Cell 5 - Get ngrok public URL:**
```python
from google.colab.output import eval_js
public_url = eval_js(f"google.colab.kernel.proxyPort({PORT})")
```

### 4. Environment Files (`backend/.env`)

```env
# Kronos Colab Integration
KRONOS_COLAB_URL=""  # Set after running notebook (e.g., https://abc123.ngrok.app)
KRONOS_COLAB_STRATEGY="cascade"  # cascade for screening, ensemble for trades
```

### 5. Test Integration (`backend/app/tests/kronos_test.py`)

Test both local and Colab:

```python
async def test_colab_integration():
    configure_colab_fallback(settings.KRONOS_COLAB_URL)
    
    strategies = ["cascade", "ensemble", "context"]
    for strategy in strategies:
        settings.KRONOS_COLAB_STRATEGY = strategy
        result = await hybrid_kronos_service.predict(symbol, ohlcv_data, forecast_horizon)
        assert result["source"] == "colab"
        assert result["status"] == "success"
```

Run with: `python -m app.tests.kronos_test`

## Strategy Selection Guide

| Strategy | Best For | Speed | Accuracy | Memory |
|----------|----------|-------|----------|--------|
| `cascade` | Screening 100s of pairs | ⚡⚡⚡ | ⭐⭐⭐ | Low |
| `ensemble` | Final trade decisions | ⚡ | ⭐⭐⭐⭐⭐ | High |
| `context` | Mixed timeframes | ⚡⚡⚡ | ⭐⭐⭐ | Medium |
| `mini` | Fastest inference | ⚡⚡⚡ | ⭐⭐ | Lowest |
| `small` | Balanced | ⚡⚡ | ⭐⭐⭐ | Medium |
| `base` | Highest single-model accuracy | ⚡ | ⭐⭐⭐⭐ | High |

**Recommended workflow:**
1. Use `cascade` for initial screening across watchlist
2. Use `ensemble` for final trade confirmation on shortlisted symbols
3. Use `context` when analyzing assets with varying history lengths

## Colab Setup Workflow

1. **Upload notebook to Colab:**
   - Go to https://colab.research.google.com/
   - Upload `kronos_colab.ipynb`

2. **Run cells in order:**
   - Cell 1: Install (2-3 min)
   - Cell 2: Load models (1-2 min)
   - Cell 3: Define functions
   - Cell 4: Start API server
   - Cell 5: Get public URL

3. **Configure backend:**
   - Copy URL from Cell 5
   - Set `KRONOS_COLAB_URL` in Settings page or `.env`

4. **Keep Colab running:**
   - Click Runtime → Never idle when asleep
   - Run Cell 6 (auto-connect) to extend session
   - Free tier: up to 12 hours/session

## Memory & Performance

**Colab free tier:**
- GPU VRAM: ~15 GB (notebook uses ~1 GB)
- System RAM: ~12.7 GB (notebook uses ~2 GB)
- Total model size: ~600 MB

**Backend (local):**
- Minimal memory (only converts OHLCV → returns)
- No GPU required
- 60-second timeout for Colab calls

## Troubleshooting

| Issue | Solution |
|-------|----------|
| URL expired | Colab URLs change per session - update after reconnect |
| 400 Bad Request | Verify Colab notebook is running, re-run Cell 4 |
| Timeout | Colab GPU busy - retry or use smaller batch |
| OOM on Colab | Use `cascade` strategy (filters early), reduce batch size |
| Strategy not applied | Check `KRONOS_COLAB_STRATEGY` in config |

## Cost Optimization

**Free tier limits:**
- Colab: 12 hours/day, may disconnect during peak hours
- GPU quota: varies, typically 15-20 GPU hours/day

**Upgrade paths:**
- Colab Pro ($10/month): Priority access, longer sessions
- Cloud GPU (Lambda Labs/Vast.ai): $0.10-0.50/hour for production

## Files Modified

- `backend/app/config.py` - Add Colab config
- `backend/app/services/kronos/hybrid_service.py` - Update `_colab_predict()`
- `backend/.env`, `backend/.env.example` - Add variables
- `backend/app/tests/kronos_test.py` - Colab integration tests
- `DEPLOYMENT.md` - Setup documentation (Part 3.25)
- `kronos_colab.ipynb` - 3-model implementation