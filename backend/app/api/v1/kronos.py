"""
Kronos forecast API routes.

Frontend calls these endpoints; the backend proxies to the Kronos service
(localhost:8001 for local dev, Modal cloud URL for production).
"""

from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List, Optional
import httpx
import os
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kronos", tags=["kronos"])

KRONOS_SERVICE_URL = settings.KRONOS_SERVICE_URL or ""
KRONOS_API_KEY = settings.KRONOS_API_KEY or ""


def _headers() -> dict:
    headers = {"accept": "application/json", "content-type": "application/json"}
    if KRONOS_API_KEY:
        headers["x-api-key"] = KRONOS_API_KEY
    return headers


async def _kronos_request(method: str, path: str, json: Optional[dict] = None,
                          params: Optional[dict] = None) -> Dict[str, Any]:
    """Proxy a request to the Kronos service."""
    if not KRONOS_SERVICE_URL:
        raise HTTPException(
            status_code=503,
            detail="Kronos service not configured. Set KRONOS_SERVICE_URL in backend/.env",
        )
    url = f"{KRONOS_SERVICE_URL.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(
                method, url, json=json, params=params, headers=_headers()
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Kronos service error: {e.response.status_code} {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Kronos service error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Kronos service request failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/health")
async def kronos_health() -> Dict[str, Any]:
    """Check Kronos service health."""
    return await _kronos_request("GET", "/health")


@router.post("/predict")
async def kronos_predict(
    symbol: str = Body(..., embed=True),
    horizon: int = Body(24, embed=True),
) -> Dict[str, Any]:
    """Predict direction for a single symbol using server-side bar acquisition."""
    return await _kronos_request(
        "GET", "/forecast",
        params={"symbol": symbol, "horizon": horizon, "limit": 400, "sample_count": 1},
    )


@router.post("/predict/batch")
async def kronos_predict_batch(
    symbols: List[str] = Body(...),
    horizon: int = Body(24),
) -> Dict[str, Any]:
    """Predict for multiple symbols in one request."""
    return await _kronos_request(
        "POST", "/forecast/batch",
        json={"symbols": symbols, "horizon": horizon, "sample_count": 1},
    )


@router.post("/forecast/closes")
async def kronos_forecast_closes(
    closes: List[float] = Body(..., embed=True),
    horizon: int = Body(30, embed=True),
    samples: int = Body(10, embed=True),
    interval_seconds: int = Body(3600, embed=True),
) -> Dict[str, Any]:
    """Forecast from close-only prices."""
    return await _kronos_request(
        "POST", "/forecast/closes",
        json={
            "closes": closes,
            "horizon": horizon,
            "samples": samples,
            "interval_seconds": interval_seconds,
        },
    )