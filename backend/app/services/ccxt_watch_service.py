"""
CCXT WatchTicker Service - real-time crypto ticker stream via WebSocket.

Subscribes to live ``watchTicker`` updates on the first geo-probed exchange
that supports it (bybit/okx/kucoin/bitget/mexc/etc.), normalizes each tick and
pushes it to the frontend WebSocket (``/ws/prices``). If no probed exchange
supports ``watchTicker``, the watcher transparently falls back to CCXT's
``fetch_ticker`` polling (used by market_data_router) so the watchlist never
goes stale.

This complements the Finnhub stock stream: crypto streams here, US stocks via
Finnhub, and any gap is covered by market_data_service's HTTP polling.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Set

import structlog

from app.config import settings
from app.api.websocket.streams import publish_price_update
from app.services.ccxt_market_data_service import (
    get_ccxt_market_data_service,
    _default_candidates,
)
from app.services.geo_probe_service import get_geo_probe_service

logger = structlog.get_logger(__name__)

_REWATCH_DELAY = 5.0  # seconds to wait before re-watching on exchange drop
_MAX_WS_RUNTIME_ERRORS = 5  # consecutive WS errors before falling back to polling


class CCXTWatchService:
    """Real-time crypto ticker watch via CCXT ``watchTicker`` with polling fallback."""

    def __init__(self) -> None:
        self._instances: Dict[str, Any] = {}
        self._symbols: Set[str] = set()
        self._running = False
        self._ws_exchange: Optional[str] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._reported_support = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, symbols: List[str]) -> None:
        """Start watching tickers for the given crypto symbols."""
        self._symbols = {s.upper() for s in symbols if s}
        self._running = True
        self._reported_support = False
        logger.info("CCXT watch service starting", symbols=sorted(self._symbols))
        if self._symbols:
            asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        for ex_id in list(self._instances.keys()):
            await self._close_exchange(ex_id)
        if self._poll_task:
            self._poll_task.cancel()
        logger.info("CCXT watch service stopped")

    async def watch(self, symbols: List[str]) -> None:
        """Dynamically add symbols to the watch (watchlist add)."""
        if not self._running:
            await self.start(symbols)
            return
        self._symbols.update(s.upper() for s in symbols if s)
        logger.info("CCXT watch symbols updated", symbols=sorted(self._symbols))

    def watched_symbols(self) -> List[str]:
        return sorted(self._symbols)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Run the watcher: choose WS exchange, stream ticks, fall back to polling."""
        try:
            exchange_ids = await self._preferred_exchanges()
        except Exception as e:  # noqa: BLE001
            logger.warning("CCXT watch: exchange probing failed", error=str(e))
            exchange_ids = _default_candidates()

        ws_exchange = await self._pick_ws_exchange(exchange_ids)
        if ws_exchange is None:
            logger.warning(
                "No probed exchange supports watchTicker; using fetch_ticker polling"
            )
            self._poll_task = asyncio.create_task(self._polling_loop())
            return

        self._ws_exchange = ws_exchange
        if not self._reported_support:
            logger.info("CCXT watchTicker stream active", exchange=self._ws_exchange)
            self._reported_support = True

        consecutive_errors = 0
        while self._running:
            try:
                ex = await self._get_exchange(self._ws_exchange)
                ticker = await ex.watch_ticker(
                    await self._native_symbol(self._ws_exchange, ex, next(iter(self._symbols)))
                )
                await self._emit(ticker)
                consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                consecutive_errors += 1
                logger.warning(
                    "CCXT watchTicker stream error",
                    exchange=self._ws_exchange,
                    error=str(e),
                    consecutive=consecutive_errors,
                )
                await self._close_exchange(self._ws_exchange)
                if consecutive_errors >= _MAX_WS_RUNTIME_ERRORS:
                    logger.warning("CCXT watchTicker giving up; switching to polling")
                    self._poll_task = asyncio.create_task(self._polling_loop())
                    return
                await asyncio.sleep(_REWATCH_DELAY)

    async def _preferred_exchanges(self) -> List[str]:
        geo = get_geo_probe_service()
        await geo.ensure_fresh()
        avail = geo.available_ccxt_exchanges()
        if avail:
            return list(avail)
        return _default_candidates()

    async def _pick_ws_exchange(self, exchange_ids: List[str]) -> Optional[str]:
        """Return the first exchange exposing a watchTicker method, else None.

        CCXT v4 reports ``has['watchTicker']`` as ``None`` ("inherited") for
        most exchanges even though the method exists and proxy-subscribes to the
        public ticker stream. We therefore probe for the callable and rely on
        the runtime-error counter + polling fallback for exchanges that reject
        the subscription.
        """
        for ex_id in exchange_ids:
            try:
                ex = await self._get_exchange(ex_id)
                if callable(getattr(ex, "watchTicker", None)):
                    return ex_id
            except Exception as e:  # noqa: BLE001
                logger.debug("CCXT watch: exchange unusable", exchange=ex_id, error=str(e))
        return None

    async def _get_exchange(self, exchange_id: str):
        if exchange_id not in self._instances:
            import ccxt.async_support as ccxt

            cls = getattr(ccxt, exchange_id)
            self._instances[exchange_id] = cls(
                {
                    "enableRateLimit": True,
                    "timeout": 10000,
                    "options": {"defaultType": "spot"},
                }
            )
        return self._instances[exchange_id]

    async def _close_exchange(self, exchange_id: str) -> None:
        ex = self._instances.pop(exchange_id, None)
        if ex is not None:
            try:
                await ex.close()
            except Exception:  # noqa: BLE001
                pass

    async def _native_symbol(self, exchange_id: str, ex, symbol: str) -> str:
        """Map 'BTC/USDT' or 'BTCUSDT' to the exchange's native format."""
        if "/" in symbol:
            return symbol
        base = symbol.replace("USDT", "").replace("USDC", "").replace("USD", "")
        return f"{base}/USDT"

    async def _emit(self, ticker: Dict[str, Any]) -> None:
        """Normalize a CCXT ticker and push to the frontend WebSocket."""
        symbol = str(ticker.get("symbol") or "").replace("/", "").replace(":", "").upper()
        price = ticker.get("last") or ticker.get("close") or ticker.get("ask")
        if not symbol or not price:
            return
        self._track_symbol(symbol)
        await publish_price_update({
            "symbol": symbol,
            "price": float(price),
            "open": ticker.get("open"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "volume": ticker.get("baseVolume"),
            "change": ticker.get("change"),
            "change_percent": ticker.get("percentage"),
            "source": f"ccxt_ws:{self._ws_exchange}",
            "timestamp": ticker.get("datetime"),
        })

    def _track_symbol(self, symbol: str) -> None:
        """Keep the emitted symbol set in sync (used by watchlist subscribers)."""
        self._symbols.add(symbol)

    async def _polling_loop(self) -> None:
        """Fallback: poll tickers via CCXT fetch_ticker every few seconds."""
        from app.services.market_data_router import get_market_data_router

        router = get_market_data_router()
        logger.info("CCXT watch: starting fetch_ticker polling fallback")
        while self._running and self._symbols:
            for symbol in list(self._symbols):
                try:
                    result = await get_ccxt_market_data_service().get_price(symbol)
                    price = result.get("price")
                    if price:
                        await publish_price_update({
                            "symbol": symbol,
                            "price": float(price),
                            "source": f"ccxt_poll:{result.get('exchange', '')}",
                            "timestamp": result.get("timestamp"),
                        })
                except Exception as e:  # noqa: BLE001
                    logger.debug("CCXT watch poll failed", symbol=symbol, error=str(e))
            if not self._running:
                break
            await asyncio.sleep(5)


_watch_service: Optional[CCXTWatchService] = None


def get_ccxt_watch_service() -> CCXTWatchService:
    """Get the CCXT watch service singleton."""
    global _watch_service
    if _watch_service is None:
        _watch_service = CCXTWatchService()
    return _watch_service