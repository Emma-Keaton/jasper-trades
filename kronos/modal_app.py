"""Modal deployment of the Kronos K-line foundation model.

Free-tier posture (Modal Starter, $30/month credit):

- CPU only. `Kronos-mini` is 4.1M parameters; a single decode costs well under a second on CPU.
- `Kronos-mini` by default (16 MB weights, 2048 context). `Kronos-small` via `KRONOS_MODEL`.
- `min_containers=0`. Scales to zero between requests; idle deployment costs nothing.
- `@modal.concurrent` lets one warm container serve several in-flight requests.

Deploy:
    modal deploy modal_app.py

Local:
    python start_kronos.py          # runs on http://localhost:8001
"""

from __future__ import annotations

import logging
import os
from typing import Any

import modal
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kronos.modal")

MODEL_VARIANT = os.getenv("KRONOS_MODEL", "NeoQuasar/Kronos-mini")

TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.4.1", index_url=TORCH_CPU_INDEX)
    .pip_install(
        "numpy",
        "pandas>=2.2,<3",
        "einops==0.8.1",
        "huggingface_hub==0.33.1",
        "safetensors==0.6.2",
        "tqdm==4.67.1",
        "fastapi[standard]==0.115.6",
        "httpx>=0.27",
    )
    .run_commands("mkdir -p /root/.cache/huggingface")
)

app = modal.App("jasper-kronos")


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


import sys
sys.path.insert(0, "/root/kronos_service")
sys.path.insert(0, "/root/kronos_lib")

from engine import Candles, KronosEngine, build_candles, build_candles_from_closes, forecast_timestamps  # noqa: E402
from gate import ForecastGate  # noqa: E402
from limits import default_policy, forecast_weight  # noqa: E402
from marketdata import MarketDataError, fetch_candles  # noqa: E402

_gate = ForecastGate()
_engine = KronosEngine(model_variant=MODEL_VARIANT)


@app.function(
    image=image,
    min_containers=0,
    concurrency_limit=10,
    cpu=2,
    memory=1024,
    timeout=300,
)
@modal.asgi_app()
def api() -> FastAPI:
    fastapi_app = FastAPI(title="Jasper Kronos Forecast Service")

    @fastapi_app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "model": MODEL_VARIANT,
            "model_loaded": _engine._loaded,
            "auth_configured": _gate.authoriser.configured,
            "device": "cpu",
            "ram_target_mb": 1024,
        }

    @fastapi_app.post("/forecast")
    async def forecast(
        request: Request,
        response: Response,
        payload: RawForecastRequest,
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        decision = _gate.admit(x_api_key, forecast_weight(payload.sample_count, payload.horizon))
        try:
            candles = build_candles(payload.candles, payload.timestamps)
            result = _engine.forecast(
                candles, payload.horizon, sample_count=payload.sample_count
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        ForecastGate.apply_headers(response, decision)
        return result

    @fastapi_app.post("/forecast/closes")
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

    @fastapi_app.post("/forecast/batch")
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

    return fastapi_app