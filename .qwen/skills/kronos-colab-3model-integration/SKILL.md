---
name: kronos-colab-3model-integration
description: DEPRECATED - Google Colab GPU hosting for Kronos removed from codebase (2026-09)
source: auto-skill
extracted_at: '2026-06-08T21:36:37.142Z'
---

# Kronos Colab 3-Model Integration — DEPRECATED

> **Status:** This integration was removed from the codebase in September 2026.
> The `colab_url` column, `KRONOS_COLAB_STRATEGY` config, `configure_colab_fallback()`,
> and `_colab_predict()` method have all been deleted.
> Kronos now runs locally via `kronos_service_4gb` with HF Inference API as the only cloud fallback.

## Overview (historical)

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

**Cell 1 - Install dependencies (with Kronos model module):**
```python
# Install dependencies
!pip install torch transformers accelerate fastapi uvicorn nest-asyncio yfinance pandas numpy pyqlib

# Clone Kronos repo to get the model module (required for NeoQuasar models)
!git clone --depth 1 https://github.com/shiyu-coder/Kronos.git /content/Kronos
!cp -r /content/Kronos/model /content/

print("✅ Dependencies installed and Kronos model module copied")
```

**Important:** The `model` module containing `Kronos`, `KronosTokenizer`, and `KronosPredictor` is NOT available via pip. It must be cloned from the official repo and copied into Colab's working directory before importing.

**Cell 2 - Load all 3 models:**
```python
import torch
from model import Kronos, KronosTokenizer, KronosPredictor
import warnings
warnings.filterwarnings('ignore')

device = "cuda" if torch.cuda.is_available() else "cpu"

# Load tokenizers first
tokenizer_base = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
tokenizer_2k = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-2k")

# Load models
model_mini = Kronos.from_pretrained("NeoQuasar/Kronos-mini")
model_small = Kronos.from_pretrained("NeoQuasar/Kronos-small")
model_base = Kronos.from_pretrained("NeoQuasar/Kronos-base")

# Create predictors with correct context lengths
predictor_mini = KronosPredictor(model_mini, tokenizer_2k, device=device, max_context=2048)
predictor_small = KronosPredictor(model_small, tokenizer_base, device=device, max_context=512)
predictor_base = KronosPredictor(model_base, tokenizer_base, device=device, max_context=512)
```

**Model-Tokenizer pairing:**
| Model | Tokenizer | Max Context |
|-------|-----------|-------------|
| Kronos-mini | Kronos-Tokenizer-2k | 2048 |
| Kronos-small | Kronos-Tokenizer-base | 512 |
| Kronos-base | Kronos-Tokenizer-base | 512 |

**Cell 3 - Implement strategies:**

The Kronos `predictor.predict()` method expects OHLCV DataFrames with timestamps, not raw return arrays:

```python
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def fetch_price_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance"""
    df = yf.download(symbol, period=f"{days}d", interval="1d", progress=False)
    df = df.reset_index()
    if 'timestamps' not in df.columns and 'Date' in df.columns:
        df['timestamps'] = pd.to_datetime(df['Date'])
    return df

def prepare_kronos_input(df: pd.DataFrame, lookback: int):
    """Prepare OHLCV DataFrame with timestamps for Kronos"""
    df = df.tail(lookback).reset_index(drop=True)
    x_df = df[['open', 'high', 'low', 'close']]
    x_timestamp = df['timestamps']
    # Create future timestamp for prediction
    last_ts = x_timestamp.iloc[-1]
    y_timestamp = pd.Series([last_ts + timedelta(days=1)])
    return x_df, x_timestamp, y_timestamp

# Strategy 1: Cascade Filtering
def predict_cascade(symbol: str, lookback_days: int = 30):
    df = fetch_price_data(symbol, lookback_days)
    
    # Step 1: Mini model as screener
    x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=100)
    mini_result = predictor_mini.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1, T=1.0, top_p=0.9, sample_count=1)
    mini_pred = mini_result['close'].iloc[-1]
    
    # Filter weak signals early
    if abs(mini_pred) < 0.001:
        return {"direction": "NEUTRAL", "confidence": 0.3, "strategy": "cascade_filtered_at_mini"}
    
    # Step 2: Small model for moderate confidence
    x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=50)
    small_result = predictor_small.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
    small_pred = small_result['close'].iloc[-1]
    
    if abs(small_pred) < 0.002:
        return {"direction": "NEUTRAL", "confidence": 0.4, "strategy": "cascade_filtered_at_small"}
    
    # Step 3: Base model for final prediction
    base_result = predictor_base.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
    base_pred = base_result['close'].iloc[-1]
    
    direction = "UP" if base_pred > 0 else "DOWN"
    return {"direction": direction, "confidence": min(abs(base_pred) * 100, 0.95), "predicted_change": base_pred}

# Strategy 2: Context-Length Routing
def predict_context_routed(symbol: str, lookback_days: int = 60):
    df = fetch_price_data(symbol, lookback_days)
    data_length = len(df)
    
    if data_length > 512:
        # Long context → mini (2048 ctx)
        x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=min(2000, data_length))
        result = predictor_mini.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
        strategy = "context_routed_mini"
    else:
        # Short context → base (best accuracy)
        x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=50)
        result = predictor_base.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
        strategy = "context_routed_base"
    
    pred = result['close'].iloc[-1]
    return {"direction": "UP" if pred > 0 else "DOWN", "predicted_change": pred, "strategy": strategy}

# Strategy 3: Model Ensembling
def predict_ensemble(symbol: str, weights=(0.2, 0.3, 0.5)):
    df = fetch_price_data(symbol, lookback_days=30)
    
    predictions = []
    
    # Mini
    x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=200)
    mini_result = predictor_mini.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
    predictions.append(mini_result['close'].iloc[-1] * weights[0])
    
    # Small
    x_df, x_ts, y_ts = prepare_kronos_input(df, lookback=50)
    small_result = predictor_small.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
    predictions.append(small_result['close'].iloc[-1] * weights[1])
    
    # Base
    base_result = predictor_base.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=1)
    predictions.append(base_result['close'].iloc[-1] * weights[2])
    
    ensemble_pred = sum(predictions)
    return {"direction": "UP" if ensemble_pred > 0 else "DOWN", "predicted_change": ensemble_pred}
```

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