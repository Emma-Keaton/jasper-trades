"""
Geo-Probe Service - runtime availability probe for Nigeria-access.

The app must never assume a service is reachable; instead it probes each one
from the actual Render region at runtime and self-prunes. This covers:

- CCXT exchanges (both market-data and live trading). Binance is included only
  when CCXT_BINANCE_OPT_IN=true AND its public market-data API responds.
- Polymarket (kept behind the same probe; disabled if the region is ineligible).

Design:
- Probing is cheap and async (single public endpoint per service).
- Results are cached in memory and refreshed hourly (or on-demand via
  /api/v1/geo/refresh).
- Exposes `is_available(service)` and `available_ccxt_exchanges()` for consumers.

Probe signals:
- HTTP 451 (or 453 for Polymarket) -> geo-ineligible -> unavailable.
- Connection errors / timeouts / Cloudflare challenge -> unavailable.
- 200 with valid data -> available.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class GeoProbeService:
    """Cached runtime availability probe for geo-sensitive services."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}  # service/key -> state
        self._refresh_interval: float = 3600.0  # 1 hour
        self._lock = asyncio.Lock()

    async def refresh(self) -> None:
        """Re-probe all configured services and update the cache."""
        async with self._lock:
            for ex in self._ccxt_candidates():
                await self._probe_ccxt_exchange(ex)
            await self._probe_polymarket()

    async def ensure_fresh(self) -> None:
        """Refresh if empty or stale (called lazily by consumers)."""
        now = time.time()
        need = not self._cache or any(
            now - s.get("probed_at", 0) > self._refresh_interval
            for s in self._cache.values()
        )
        if need:
            await self.refresh()

    def is_available(self, service: str) -> bool:
        state = self._cache.get(service)
        return bool(state and state.get("available"))

    def available_ccxt_exchanges(self) -> List[str]:
        """Return exchange IDs whose public market-data probe succeeded."""
        return [
            s.replace("ccxt:", "")
            for s, state in self._cache.items()
            if s.startswith("ccxt:") and state.get("available")
        ]

    def polymorphy_available(self) -> bool:
        return self.is_available("polymarket")

    def status(self) -> Dict[str, Any]:
        return {
            "ccxt_exchanges": {
                ex: self._cache.get(f"ccxt:{ex}", {}).get("available", False)
                for ex in self._ccxt_candidates()
            },
            "polymarket": self.is_available("polymarket"),
            "probed_at": max(
                (s.get("probed_at", 0) for s in self._cache.values()), default=0
            ),
        }

    def _ccxt_candidates(self) -> List[str]:
        raw = settings.CCXT_EXCHANGES
        candidates = [x.strip().lower() for x in raw.split(",") if x.strip()]
        if settings.CCXT_BINANCE_OPT_IN and "binance" not in candidates:
            candidates.append("binance")
        return candidates

    async def _probe_ccxt_exchange(self, exchange_id: str) -> None:
        """Probe an exchange's public market-data endpoint (no credentials)."""
        key = f"ccxt:{exchange_id}"
        reason: Optional[str] = None
        try:
            import ccxt.async_support as ccxt

            exchange_class = getattr(ccxt, exchange_id)
            ex = exchange_class({"enableRateLimit": False, "timeout": 8000})
            try:
                ticker = await ex.fetch_ticker("BTC/USDT")
                ok = ticker is not None and ticker.get("last") is not None
                if not ok:
                    reason = "no ticker data"
            finally:
                await ex.close()
        except Exception as e:  # noqa: BLE001
            ok = False
            reason = self._classify_error(str(e))

        self._cache[key] = {"available": ok, "reason": reason, "probed_at": time.time()}
        if not ok:
            logger.info(
                "Geo-probe: exchange unavailable (pruned)",
                exchange=exchange_id,
                reason=reason,
            )

    async def _probe_polymarket(self) -> None:
        """Probe Polymarket's public Gamma API; 453/block -> unavailable."""
        key = "polymarket"
        url = "https://gamma-api.polymarket.com/markets/keyset"
        params = {"closed": "false", "limit": "1"}
        reason: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
            if resp.status_code == 200:
                ok = True
            elif resp.status_code in (451, 453):
                ok = False
                reason = f"geo-ineligible (HTTP {resp.status_code})"
            else:
                ok = False
                reason = f"HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001
            ok = False
            reason = self._classify_error(str(e))

        self._cache[key] = {"available": ok, "reason": reason, "probed_at": time.time()}
        if not ok:
            logger.info("Geo-probe: Polymarket disabled", reason=reason)

    @staticmethod
    def _classify_error(msg: str) -> str:
        low = msg.lower()
        if "451" in low or "unavailable_for_legal" in low:
            return "geo-ineligible (451)"
        if "453" in low or ("location" in low and "not" in low):
            return "geo-ineligible (453)"
        if "timed out" in low or "timeout" in low:
            return "timeout"
        if "cloudflare" in low or "forbidden" in low or "403" in low:
            return "blocked (Cloudflare/403)"
        if "connect" in low or "no connection" in low or "network" in low:
            return "connection-failed"
        return (msg[:120]) or "unknown"


_geo_probe: Optional[GeoProbeService] = None


def get_geo_probe_service() -> GeoProbeService:
    global _geo_probe
    if _geo_probe is None:
        _geo_probe = GeoProbeService()
    return _geo_probe

