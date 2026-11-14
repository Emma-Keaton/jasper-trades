#!/usr/bin/env python3
"""
Jasper Kronos — Local Service Starter

Runs the Kronos forecast service locally on http://localhost:8001 (or
$KRONOS_LOCAL_PORT). Intended for development on a 2GB RAM laptop.

Uses Kronos-mini (4.1M params, ~16 MB weights) downloaded from Hugging Face
on first launch and cached in ~/.cache/huggingface.

Usage:
    cd kronos
    python start_kronos.py

Environment variables (from .env):
    KRONOS_SERVICE_URL   # not needed for local mode
    KRONOS_API_KEY       # required to protect endpoints
    KRONOS_MODEL         # NeoQuasar/Kronos-mini (default)
    KRONOS_LOCAL_PORT    # 8001 (default)
"""

from __future__ import annotations

import os
import sys
import uvicorn

# Ensure local packages are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kronos_service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kronos_lib"))

from fastapi import FastAPI
from gate import ForecastGate
from limits import default_policy, forecast_weight
from marketdata import MarketDataError, fetch_candles
from engine import KronosEngine, build_candles, build_candles_from_closes

from pydantic import BaseModel, Field
from typing import Any
from fastapi import Header, HTTPException, Query, Request, Response


MODEL_VARIANT = os.getenv("KRONOS_MODEL", "NeoQuasar/Kronos-mini")
LOCAL_PORT = int(os.getenv("KRONOS_LOCAL_PORT", "8001"))

app = FastAPI(title="Jasper Kronos Forecast Service (Local)")

_gate = ForecastGate()
_engine = KronosEngine(model_variant=MODEL_VARIANT)


class RawForecastRequest(BaseModel):
    candles: list[dict[str, Any]] = Field(..., min_length=16)
    timestamps: list[str] | None = None
    horizon: int = Field(24, ge=1, le=512)
    sample_count: int = Field(1, ge=1, le=32)


class ClosesForecastRequest(BaseModel):
    closes: list[float] = Field(..., min_length=16)
    horizon: int = Field(30, ge=1, le=512)
    samples: int = Field(10, ge=1, le=64)
    interval_seconds: int = Field(3600, ge=1, le=86400)
    timestamps: list[str] | None = None


class BatchForecastRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=50)
    interval: str = Field("1h")
    limit: int = Query(400, ge=16, le=1000)
    horizon: int = Field(24, ge=1, le=512)
    sample_count: int = Field(1, ge=1, le=32)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "model": MODEL_VARIANT,
        "model_loaded": _engine._loaded,
        "auth_configured": _gate.authoriser.configured,
        "device": "cpu",
        "mode": "local",
        "port": LOCAL_PORT,
    }


@app.post("/forecast")
async def forecast(
    request: Request,
    response: Response,
    payload: RawForecastRequest,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    decision = _gate.admit(x_api_key, forecast_weight(payload.sample_count, payload.horizon))
    try:
        candles = build_candles(payload.candles, payload.timestamps)
        result = _engine.forecast(candles, payload.horizon, sample_count=payload.sample_count)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    ForecastGate.apply_headers(response, decision)
    return result


@app.post("/forecast/closes")
async def forecast_closes(
    request: Request,
    response: Response,
    payload: ClosesForecastRequest,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    decision = _gate.admit(x_api_key, forecast_weight(payload.samples, payload.horizon))
    try:
        candles = build_candles_from_closes(
            payload.closes,
            interval_seconds=payload.interval_seconds,
            timestamps=payload.timestamps,
        )
        result = _engine.forecast(candles, payload.horizon, sample_count=payload.samples)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    ForecastGate.apply_headers(response, decision)
    return result


@app.post("/forecast/batch")
async def forecast_batch(
    request: Request,
    response: Response,
    payload: BatchForecastRequest,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    unit_weight = forecast_weight(payload.sample_count, payload.horizon)
    total_weight = unit_weight * len(payload.symbols)
    decision = _gate.admit(x_api_key, total_weight, unit_weight=unit_weight)
    results: dict[str, Any] = {}
    for symbol in payload.symbols:
        try:
            candles = fetch_candles(symbol, interval=payload.interval, limit=payload.limit)
        except MarketDataError as error:
            results[symbol] = {"error": str(error)}
            continue
        try:
            results[symbol] = _engine.forecast(
                candles, payload.horizon, sample_count=payload.sample_count
            )
        except ValueError as error:
            results[symbol] = {"error": str(error)}
    ForecastGate.apply_headers(response, decision)
    return {"results": results}


def main() -> None:
    print("=" * 50)
    print("Jasper Kronos — Local Forecast Service")
    print("=" * 50)
    print(f"Model:    {MODEL_VARIANT}")
    print(f"Port:     http://localhost:{LOCAL_PORT}")
    print(f"Docs:     http://localhost:{LOCAL_PORT}/docs")
    print(f"Health:   http://localhost:{LOCAL_PORT}/health")
    print()
    print("First launch downloads Kronos-mini from Hugging Face (~16 MB).")
    print("This may take 1–3 minutes depending on your connection.")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print()

    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)


if __name__ == "__main__":
    main()