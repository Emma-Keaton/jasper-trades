"""Client for the kronos forecast service.

Point trading apps at the local kronos service (preferred for localhost dev)
or at the deployed Modal URL (cloud).

    export KRONOS_SERVICE_URL=http://localhost:8001   # local
    export KRONOS_SERVICE_URL=https://<modal-url>      # cloud
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_TIMEOUT = 60.0


@dataclass
class KronosClient:
    """Thin synchronous client for the `/forecast` surface."""

    base_url: str = field(
        default_factory=lambda: os.getenv("KRONOS_SERVICE_URL", "").rstrip("/")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("KRONOS_API_KEY", "")
    )
    timeout: float = DEFAULT_TIMEOUT

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError(
                "KRONOS_SERVICE_URL is unset; point it at the local kronos "
                "service (http://localhost:8001) or the deployed Modal URL"
            )

    def _headers(self) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def health(self) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/health", headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def forecast_symbol(
        self,
        symbol: str,
        *,
        interval: str = "1h",
        horizon: int = 24,
        limit: int = 400,
        sample_count: int = 1,
    ) -> dict[str, Any]:
        """Forecast `symbol` using server-side bar acquisition."""
        params = {
            "symbol": symbol,
            "interval": interval,
            "horizon": horizon,
            "limit": limit,
            "sample_count": sample_count,
        }
        started = time.monotonic()
        response = httpx.get(
            f"{self.base_url}/forecast",
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        payload["_round_trip_ms"] = round((time.monotonic() - started) * 1000, 1)
        payload["_cache"] = response.headers.get("x-kronos-cache", "DIRECT")
        return payload

    def forecast_candles(
        self,
        candles: list[dict[str, Any]],
        *,
        horizon: int = 24,
        timestamps: list[str] | None = None,
        sample_count: int = 1,
    ) -> dict[str, Any]:
        """Forecast caller-supplied OHLCV rows (no market-data lookup)."""
        body: dict[str, Any] = {
            "candles": candles,
            "horizon": horizon,
            "sample_count": sample_count,
        }
        if timestamps is not None:
            body["timestamps"] = timestamps
        response = httpx.post(
            f"{self.base_url}/forecast",
            json=body,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()