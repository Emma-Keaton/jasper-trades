"""
Kronos replacement fallback (aegis-quant forecasting system).

When the remote Kronos service is not configured or unreachable, this module
produces a real directional prediction from the lightweight tiered forecaster
(statsmodels -> deterministic) instead of a neutral placeholder. The returned
dict matches the shape consumed by signal confidence scoring (direction,
confidence, no `error` key on success).
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.data_connectors import data_connector_service
from app.services.forecasting import get_forecasting_service

logger = logging.getLogger(__name__)

# Need at least this many closes for the replacement forecaster to say anything.
MIN_CLOSES = 16


async def fetch_closes(symbol: str, range_: str = "6mo") -> List[float]:
    """Fetch ~6 months of daily closes for a symbol (keyless Yahoo chart)."""
    try:
        ohlcv = await data_connector_service.get_yfinance_data(symbol, interval="1d", range_=range_)
    except Exception as e:  # noqa: BLE001
        logger.warning("Replacement forecast: data fetch failed for %s: %s", symbol, e)
        return []
    closes = []
    for bar in ohlcv or []:
        try:
            closes.append(float(bar["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    return closes


async def replacement_prediction(
    symbol: str,
    lookback_days: int = 30,
    range_: str = "6mo",
) -> Optional[Dict[str, Any]]:
    """
    Build a Kronos-shaped prediction from the replacement forecaster.

    Returns None when there isn't enough price data, in which case the caller
    keeps its neutral/error placeholder.
    """
    closes = await fetch_closes(symbol, range_=range_)
    if len(closes) < MIN_CLOSES:
        logger.info("Replacement forecast for %s: insufficient data (%d closes)", symbol, len(closes))
        return None

    horizon = max(10, lookback_days or 30)
    try:
        result = await get_forecasting_service().forecast(
            symbol=symbol, closes=closes, horizon=horizon, samples=30
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Replacement forecast failed for %s: %s", symbol, e)
        return None

    last_close = float(closes[-1])
    target = float(result.mean_path[-1]) if result.mean_path else last_close
    direction = "UP" if target >= last_close else "DOWN"
    confidence = max(0.0, min(1.0, float(result.confidence) / 100.0))
    model_source = result.metadata.get("model_source", "deterministic")

    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": round(confidence, 3),
        "strategy": f"replacement_{model_source}",
        "model_source": model_source,
        "predicted_change": round(target - last_close, 6),
        "mean_path": result.mean_path,
        "confidence_90": result.confidence_90,
        "metadata": result.metadata,
    }
