"""
CCXT Market Data Service - ordered multi-exchange polling.

Polls live market data (price / OHLCV / orderbook / symbols) from a Nigeria-
accessible CEX set discovered by the GeoProbeService. On failure of one
exchange the service transparently fails over to the next available one.

No API keys are required for public market data. Crypto LIVE trading (with
user keys) is handled separately by app/brokers/ccxt_service.py.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.config import settings
from app.services.geo_probe_service import get_geo_probe_service

logger = structlog.get_logger(__name__)


def _default_candidates() -> List[str]:
    raw = settings.CCXT_EXCHANGES
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


class CCXTMarketDataService:
    """Multi-exchange CCXT market-data poller with failover."""

    def __init__(self) -> None:
        self._geo = get_geo_probe_service()
        self._instances: Dict[str, Any] = {}
        self._allowed: Optional[List[str]] = None
        self._symbol_cache: Dict[str, List[str]] = {}

    async def _allowed_exchanges(self) -> List[str]:
        """Probe-passed exchanges OR the default set if nothing probed yet."""
        await self._geo.ensure_fresh()
        avail = self._geo.available_ccxt_exchanges()
        if avail:
            self._allowed = avail
            return avail
        candidates = _default_candidates()
        if settings.CCXT_BINANCE_OPT_IN and "binance" not in candidates:
            candidates.append("binance")
        self._allowed = candidates
        return candidates

    async def _get_exchange(self, exchange_id: str):
        if exchange_id not in self._instances:
            import ccxt.async_support as ccxt

            cls = getattr(ccxt, exchange_id)
            self._instances[exchange_id] = cls(
                {"enableRateLimit": True, "timeout": 10000}
            )
        return self._instances[exchange_id]

    async def _close_exchange(self, exchange_id: str) -> None:
        ex = self._instances.pop(exchange_id, None)
        if ex is not None:
            try:
                await ex.close()
            except Exception:  # noqa: BLE001
                pass

    async def _call(
        self, method: str, symbol: str, *args, **kwargs
    ) -> Tuple[Any, str]:
        """Call `method` on each available exchange in order until one succeeds."""
        exchanges = await self._allowed_exchanges()
        last_error: Optional[Exception] = None
        for exchange_id in exchanges:
            try:
                ex = await self._get_exchange(exchange_id)
                fn = getattr(ex, method)
                norm_symbol = await self._normalize_symbol(exchange_id, ex, symbol)
                result = await fn(norm_symbol, *args, **kwargs)
                if result is not None:
                    return result, exchange_id
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.debug(
                    "CCXT call failed; trying next",
                    method=method, exchange=exchange_id, symbol=symbol, error=str(e),
                )
        raise RuntimeError(
            f"CCXT {method}({symbol}) failed on all exchanges. Last error: {last_error}"
        )

    async def _normalize_symbol(self, exchange_id: str, ex, symbol: str) -> str:
        """Map 'BTC/USDT' or 'BTCUSDT' to the exchange's native format."""
        target = symbol.upper()
        if "/" in target:
            base, quote = target.split("/")
            resolved = await self._resolve_pair(ex, base, quote)
            return resolved or target
        if target.endswith("USDT"):
            return f"{target[:-4]}/USDT"
        return target

    async def _resolve_pair(self, ex, base: str, quote: str) -> Optional[str]:
        try:
            markets = await ex.load_markets()
        except Exception:  # noqa: BLE001
            return None
        for cand in (f"{base}/{quote}", f"{base}/USDT", f"{base}/USD"):
            if cand in markets:
                return cand
        for sym, mkt in markets.items():
            if mkt.get("base") == base and mkt.get("quote") in (quote, "USDT", "USD"):
                return sym
        return None

    async def get_price(self, symbol: str) -> Dict[str, Any]:
        ticker, exchange_id = await self._call("fetch_ticker", symbol)
        return {
            "symbol": symbol,
            "price": float(ticker.get("last") or 0),
            "exchange": exchange_id,
            "timestamp": ticker.get("timestamp"),
        }

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> List[List[float]]:
        ohlcv, _ = await self._call("fetch_ohlcv", symbol, timeframe, limit=limit)
        return [[float(x) if x is not None else 0.0 for x in row] for row in ohlcv]

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        ob, exchange_id = await self._call("fetch_order_book", symbol, depth)
        return {
            "symbol": symbol,
            "bids": [[float(x), float(y)] for x, y in (ob.get("bids") or [])][:depth],
            "asks": [[float(x), float(y)] for x, y in (ob.get("asks") or [])][:depth],
            "exchange": exchange_id,
            "timestamp": ob.get("timestamp"),
        }

    async def get_supported_symbols(self, exchange_id: Optional[str] = None) -> List[str]:
        """Return a union of tradeable symbols across the top exchanges."""
        exchanges = await self._allowed_exchanges()
        if exchange_id and exchange_id in exchanges:
            exchanges = [exchange_id]
        all_symbols: set = set()
        for ex_id in exchanges[:5]:
            if ex_id in self._symbol_cache:
                all_symbols.update(self._symbol_cache[ex_id])
                continue
            try:
                ex = await self._get_exchange(ex_id)
                markets = await ex.load_markets()
                symbols = [s for s in markets.keys() if "/" in s]
                all_symbols.update(symbols)
                self._symbol_cache[ex_id] = symbols
            except Exception as e:  # noqa: BLE001
                logger.debug("Could not load markets", exchange=ex_id, error=str(e))
        return sorted(all_symbols)

    async def shutdown(self) -> None:
        for ex_id in list(self._instances.keys()):
            await self._close_exchange(ex_id)


_market_data: Optional[CCXTMarketDataService] = None


def get_ccxt_market_data_service() -> CCXTMarketDataService:
    global _market_data
    if _market_data is None:
        _market_data = CCXTMarketDataService()
    return _market_data

