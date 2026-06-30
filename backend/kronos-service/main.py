# Kronos Service - Render Deployment
# Simplified time-series forecasting service for Jasper Trades
# CPU-optimized, low memory footprint

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import torch
import torch.nn as nn
import asyncio
import os
import time
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Model cache (single model at a time)
_model_cache: Dict[str, Any] = {}
_last_access_time: float = time.time()
MODEL_UNLOAD_TIMEOUT = int(os.getenv("MODEL_UNLOAD_TIMEOUT", "300"))

# ============================================================
# Model Definitions (Lightweight Time-Series Models)
# ============================================================

class LSTMForecaster(nn.Module):
    """Lightweight LSTM for time series forecasting."""
    def __init__(self, input_size=4, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])

class TransformerForecaster(nn.Module):
    """Lightweight transformer for time series."""
    def __init__(self, input_size=4, d_model=32, nhead=4, num_layers=2):
        super().__init__()
        self.embedding = nn.Linear(input_size, d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True, dropout=0.1)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(d_model, 1)
    
    def forward(self, x):
        x = self.embedding(x)
        x = self.encoder(x)
        return self.fc(x[:, -1, :])

# Model configuration
MODEL_CONFIG = {
    "kronos-mini": {"type": "lstm", "hidden_size": 32, "num_layers": 1},
    "kronos-small": {"type": "transformer", "d_model": 32, "nhead": 4, "num_layers": 1},
    "kronos-base": {"type": "transformer", "d_model": 64, "nhead": 8, "num_layers": 2},
}

def create_model(model_name: str) -> nn.Module:
    """Create model architecture."""
    config = MODEL_CONFIG.get(model_name, MODEL_CONFIG["kronos-mini"])
    
    if config["type"] == "lstm":
        return LSTMForecaster(
            input_size=4,
            hidden_size=config.get("hidden_size", 64),
            num_layers=config.get("num_layers", 2)
        )
    else:
        return TransformerForecaster(
            input_size=4,
            d_model=config.get("d_model", 32),
            nhead=config.get("nhead", 4),
            num_layers=config.get("num_layers", 2)
        )

# ============================================================
# Model Loading
# ============================================================

async def load_model(model_name: str) -> nn.Module:
    """
    Load model on-demand (not at startup).
    Unloads previous model to save memory.
    """
    global _model_cache, _last_access_time
    
    if model_name in _model_cache:
        _last_access_time = time.time()
        return _model_cache[model_name]
    
    logger.info(f"Loading model: {model_name}")
    
    try:
        # Unload existing model
        if _model_cache:
            logger.info("Unloading previous model to free memory")
            _model_cache.clear()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # Create model
        model = create_model(model_name)
        
        # Try to load pre-trained weights from HF (if available)
        try:
            from huggingface_hub import hf_hub_download
            model_file = hf_hub_download(
                repo_id=f"NeoQuasar/{model_name}",
                filename="pytorch_model.bin",
                cache_dir="/tmp/kronos_models"
            )
            model.load_state_dict(torch.load(model_file, map_location="cpu", weights_only=True))
            logger.info(f"Loaded pre-trained weights for {model_name}")
        except Exception as e:
            logger.warning(f"No pre-trained weights found: {e}. Using random initialization.")
        
        model.eval()
        _model_cache[model_name] = model
        _last_access_time = time.time()
        
        logger.info(f"Successfully loaded {model_name} on CPU")
        return model
        
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Model loading failed: {str(e)}")

def unload_model():
    """Unload model to free memory."""
    global _model_cache
    if _model_cache:
        logger.info("Unloading model to free memory")
        _model_cache.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

async def check_model_timeout():
    """Check if model should be unloaded."""
    global _last_access_time
    if _model_cache:
        elapsed = time.time() - _last_access_time
        if elapsed > MODEL_UNLOAD_TIMEOUT:
            unload_model()

# ============================================================
# Data Processing
# ============================================================

def fetch_price_data(symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
    """Fetch historical price data."""
    try:
        df = yf.download(symbol, period=f"{days}d", interval="1d", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        return df.dropna()
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

def prepare_sequence(df: pd.DataFrame, lookback: int) -> Optional[np.ndarray]:
    """Prepare normalized sequence for model input."""
    if len(df) < lookback:
        return None
    
    # Extract OHLCV features
    scaler = MinMaxScaler()
    data = df[['open', 'high', 'low', 'close']].values[-lookback:]
    scaled = scaler.fit_transform(data)
    
    # Create sequence (batch, time, features) -> reshaped to (lookback, 4)
    return scaled

def model_predict(model: nn.Module, sequence: np.ndarray) -> float:
    """Run model inference."""
    model.eval()
    with torch.no_grad():
        x = torch.FloatTensor(sequence).unsqueeze(0)  # Add batch dimension
        output = model(x)
        return output.item()

# ============================================================
# Prediction Strategies
# ============================================================

async def predict_single(symbol: str, model_name: str, lookback_days: int = 30) -> Dict:
    """Single model prediction."""
    start_time = time.time()
    
    df = fetch_price_data(symbol, lookback_days)
    if df is None or len(df) < 20:
        return {"symbol": symbol, "direction": "UNKNOWN", "confidence": 0.0, "error": "Insufficient data"}
    
    try:
        model = await load_model(model_name)
        
        # Determine lookback based on model
        lookback = 200 if "mini" in model_name else 50
        if len(df) < lookback:
            lookback = len(df)
        
        sequence = prepare_sequence(df, lookback)
        if sequence is None:
            return {"symbol": symbol, "direction": "ERROR", "confidence": 0.0, "error": "Data preparation failed"}
        
        # Get prediction
        pred = model_predict(model, sequence)
        
        # Convert to directional signal
        direction = "UP" if pred > 0 else "DOWN"
        confidence = min(abs(pred) * 100, 0.95)
        
        return {
            "symbol": symbol,
            "direction": direction,
            "confidence": round(confidence, 3),
            "predicted_change": round(pred, 6),
            "strategy": f"single_{model_name}",
            "timestamp": datetime.utcnow().isoformat(),
            "inference_time_ms": round((time.time() - start_time) * 1000, 2)
        }
        
    except Exception as e:
        logger.error(f"Prediction failed for {symbol}: {e}")
        return {"symbol": symbol, "direction": "ERROR", "confidence": 0.0, "error": str(e)}

async def predict_cascade(symbol: str, lookback_days: int = 30) -> Dict:
    """Cascade strategy (mini -> small)."""
    start_time = time.time()
    
    df = fetch_price_data(symbol, lookback_days)
    if df is None or len(df) < 20:
        return {"symbol": symbol, "direction": "UNKNOWN", "confidence": 0.0, "error": "Insufficient data"}
    
    # Step 1: Mini model
    try:
        mini_model = await load_model("kronos-mini")
        lookback = min(100, len(df))
        sequence = prepare_sequence(df, lookback)
        if sequence is not None:
            mini_pred = model_predict(mini_model, sequence)
            
            if abs(mini_pred) < 0.001:
                return {
                    "symbol": symbol,
                    "direction": "NEUTRAL",
                    "confidence": 0.3,
                    "strategy": "cascade_filtered_at_mini",
                    "timestamp": datetime.utcnow().isoformat(),
                    "inference_time_ms": round((time.time() - start_time) * 1000, 2)
                }
        else:
            mini_pred = 0
    except Exception as e:
        logger.warning(f"Mini model failed: {e}")
        mini_pred = 0
    
    # Step 2: Small model
    try:
        small_model = await load_model("kronos-small")
        lookback = min(50, len(df))
        sequence = prepare_sequence(df, lookback)
        if sequence is not None:
            small_pred = model_predict(small_model, sequence)
            
            if abs(small_pred) < 0.002:
                return {
                    "symbol": symbol,
                    "direction": "NEUTRAL",
                    "confidence": 0.4,
                    "strategy": "cascade_filtered_at_small",
                    "timestamp": datetime.utcnow().isoformat(),
                    "inference_time_ms": round((time.time() - start_time) * 1000, 2)
                }
        else:
            small_pred = mini_pred
    except Exception as e:
        logger.warning(f"Small model failed: {e}")
        small_pred = mini_pred
    
    direction = "UP" if small_pred > 0 else "DOWN"
    confidence = min(abs(small_pred) * 100, 0.95)
    
    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": round(confidence, 3),
        "predicted_change": round(small_pred, 6),
        "strategy": "cascade_cpu",
        "timestamp": datetime.utcnow().isoformat(),
        "inference_time_ms": round((time.time() - start_time) * 1000, 2)
    }

async def predict_ensemble(symbol: str, lookback_days: int = 30) -> Dict:
    """Ensemble prediction (weighted average)."""
    start_time = time.time()
    
    df = fetch_price_data(symbol, lookback_days)
    if df is None or len(df) < 20:
        return {"symbol": symbol, "direction": "UNKNOWN", "confidence": 0.0, "error": "Insufficient data"}
    
    weights = {"kronos-mini": 0.4, "kronos-small": 0.6}
    predictions = []
    
    for model_name, weight in weights.items():
        try:
            model = await load_model(model_name)
            lookback = 200 if "mini" in model_name else 50
            lookback = min(lookback, len(df))
            
            sequence = prepare_sequence(df, lookback)
            if sequence is not None:
                pred = model_predict(model, sequence)
                predictions.append(pred * weight)
        except Exception as e:
            logger.warning(f"{model_name} failed in ensemble: {e}")
    
    if not predictions:
        return {"symbol": symbol, "direction": "ERROR", "confidence": 0.0, "error": "All models failed"}
    
    ensemble_pred = sum(predictions)
    direction = "UP" if ensemble_pred > 0 else "DOWN"
    confidence = min(abs(ensemble_pred) * 100, 0.95)
    
    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": round(confidence, 3),
        "predicted_change": round(ensemble_pred, 6),
        "strategy": "ensemble_cpu",
        "weights": weights,
        "timestamp": datetime.utcnow().isoformat(),
        "inference_time_ms": round((time.time() - start_time) * 1000, 2)
    }

# ============================================================
# FastAPI App
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Kronos Service starting (CPU-optimized)")
    logger.info("Models will be loaded on-demand")
    
    yield
    
    if _model_cache:
        unload_model()
    logger.info("Kronos Service shut down")

app = FastAPI(
    title="Kronos Prediction API (Render)",
    description="Time-series forecasting with Kronos models for Jasper Trades (CPU-only, 512MB RAM)",
    version="2.1.0-render",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# API Endpoints
# ============================================================

class BatchRequest(BaseModel):
    symbols: List[str]
    strategy: Optional[str] = "cascade"
    lookback_days: Optional[int] = 30

@app.get("/")
async def root():
    return {
        "service": "Kronos Prediction API (Render)",
        "version": "2.1.0-render",
        "models": ["kronos-mini", "kronos-small", "kronos-base"],
        "strategies": ["cascade", "ensemble", "mini", "small", "base"],
        "status": "running",
        "gpu_available": False,
        "device": "cpu",
        "memory_optimized": True
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "models_loaded": list(_model_cache.keys()),
        "gpu_available": False,
        "device": "cpu",
        "uptime_check": time.time()
    }

@app.get("/predict/{symbol}")
async def predict(symbol: str, strategy: str = "cascade", lookback_days: int = 30):
    """Get prediction for a single symbol."""
    await check_model_timeout()
    
    if strategy == "cascade":
        return await predict_cascade(symbol, lookback_days)
    elif strategy == "ensemble":
        return await predict_ensemble(symbol, lookback_days)
    elif strategy in ["mini", "small", "base"]:
        return await predict_single(symbol, f"kronos-{strategy}", lookback_days)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

@app.post("/predict/batch")
async def predict_batch(request: BatchRequest):
    """Get predictions for multiple symbols."""
    results = {}
    for symbol in request.symbols:
        results[symbol] = await predict(symbol, request.strategy, request.lookback_days)
    return results

@app.get("/test")
async def test_prediction():
    """Test prediction with AAPL."""
    return await predict("AAPL", "cascade", 30)

@app.get("/strategies")
async def list_strategies():
    """List available strategies."""
    return {
        "strategies": [
            {"name": "cascade", "description": "Sequential filtering (mini → small)", "use_case": "Screening pairs", "speed": "⚡⚡"},
            {"name": "ensemble", "description": "Weighted avg (mini + small)", "use_case": "Robustness", "speed": "⚡"},
            {"name": "mini", "description": "Kronos-mini only", "use_case": "Fast inference", "speed": "⚡⚡⚡"},
            {"name": "small", "description": "Kronos-small only", "use_case": "Balanced", "speed": "⚡⚡"},
            {"name": "base", "description": "Kronos-base only", "use_case": "Highest accuracy", "speed": "⚡"}
        ]
    }

@app.post("/model/load")
async def preload_model(model_name: str):
    """Preload a specific model (optional)."""
    try:
        await load_model(model_name)
        return {"status": "loaded", "model": model_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/model/unload")
async def unload_all_models():
    """Unload all models to free memory."""
    unload_model()
    return {"status": "unloaded", "models_loaded": list(_model_cache.keys())}