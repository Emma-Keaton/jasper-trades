"""Bar data acquisition for forecast requests.

Three keyless sources, tried in order: Binance, Yahoo Finance, Stooq.
Results are memoised per (source, symbol, interval).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import httpx
import pandas as pd

from .engine import Candles, build_candles

logger = logging.getLogger("kronos.marketdata")

STOOQ_URL = "https://stooq.com/q/d/l/"
BINANCE_URLS = (
    "https://api.binance.com/api/v3/klines",
    "https://api.binance.us/api/v3/klines",
)
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

YAHOO_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
YAHOO_RANGE = {"1m": "7d", "5m": "60d", "15m": "60d", "1h": "730d", "1d": "5y"}
INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}

USER_AGENT = "Mozilla/5.0 (compatible; jasper-kronos/1.0)"
BINANCE_MAX_LIMIT = 1000
CACHE_TTL_SECONDS = 60.0
MAX_CACHE_ENTRIES = 512
REQUEST_TIMEOUT = 20.0


class MarketDataError(RuntimeError):
    """Upstream bar source failed or returned unusable data."""


class _TTLCache:
    def __init__(self, ttl: float, max_entries: int) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._entries: dict[tuple[str, ...], tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[str, ...]) -> Any | None:
        now = time.monotonic()
        with self._lock:
            hit = self._entries.get(key)
            if hit is None:
                return None
            stored_at, value = hit
            if now - stored_at > self._ttl:
                del self._entries[key]
                return None
            return value

    def put(self, key: tuple[str, ...], value: Any) -> None:
        with self._lock:
            if len(self._entries) >= self._max:
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                del self._entries[oldest]
            self._entries[key] = (time.monotonic(), value)


_cache = _TTLCache(CACHE_TTL_SECONDS, MAX_CACHE_ENTRIES)


def _is_crypto(symbol: str) -> bool:
    return symbol.endswith(("-USDT", "-USDC", "-BTC")) or "/" in symbol


def _sources_for(symbol: str) -> list:
    if _is_crypto(symbol):
        return [("binance", _fetch_binance), ("yahoo", _fetch_yahoo), ("stooq", _fetch_stooq)]
    return [("yahoo", _fetch_yahoo), ("stooq", _fetch_stooq), ("binance", _fetch_binance)]


def _fetch_yahoo(symbol: str, interval: str, limit: int) -> list:
    ticker = symbol.replace("-", "").replace("/", "")
    url = YAHOO_URL.format(symbol=ticker)
    params = {
        "range": YAHOO_RANGE.get(interval, "730d"),
        "interval": YAHOO_INTERVALS.get(interval, "1h"),
    }
    try:
        response = httpx.get(
            url, params=params, timeout=REQUEST_TIMEOUT, headers={"user-agent": USER_AGENT}
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise MarketDataError(f"yahoo failed for {symbol}: {error}") from error

    chart = data.get("chart", {})
    result = chart.get("result", [None])[0]
    if not result:
        raise MarketDataError(f"yahoo returned no result for {symbol}")

    timestamps = result.get("timestamp", [])
    indicators = result.get("indicators", {})
    quote = indicators.get("quote", [None])[0]
    if not quote:
        raise MarketDataError(f"yahoo returned no quote data for {symbol}")

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    rows = []
    for i, epoch in enumerate(timestamps):
        values = [
            opens[i] if i < len(opens) else None,
            highs[i] if i < len(highs) else None,
            lows[i] if i < len(lows) else None,
            closes[i] if i < len(closes) else None,
        ]
        if any(v is None for v in values):
            continue
        rows.append(
            {
                "timestamp": pd.to_datetime(epoch, unit="s", utc=True).isoformat(),
                "open": float(values[0]),
                "high": float(values[1]),
                "low": float(values[2]),
                "close": float(values[3]),
                "volume": float(volumes[i]) if i < len(volumes) and volumes[i] else 0.0,
            }
        )
    if not rows:
        raise MarketDataError(f"yahoo returned no usable bars for {symbol} at {interval}")
    return rows[-limit:]


def _fetch_binance(symbol: str, interval: str, limit: int) -> list:
    pair = symbol.replace("/", "").replace("-", "").upper()
    params = {
        "symbol": pair,
        "interval": INTERVALS.get(interval, "1h"),
        "limit": min(limit, BINANCE_MAX_LIMIT),
    }
    errors: list[str] = []
    for base in BINANCE_URLS:
        try:
            response = httpx.get(
                base, params=params, timeout=REQUEST_TIMEOUT, headers={"user-agent": USER_AGENT}
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            errors.append(f"{base.split('//')[1][:12]}: {error}")
            continue

        if isinstance(payload, list) and payload:
            return [
                {
                    "timestamp": pd.to_datetime(candle[0], unit="ms", utc=True).isoformat(),
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5],
                }
                for candle in payload
            ][-limit:]
        errors.append(f"{base.split('//')[1][:12]}: empty klines")

    raise MarketDataError(
        f"binance has no klines for {pair!r} at {interval} ({'; '.join(errors)})"
    )


def _fetch_stooq(symbol: str, interval: str, limit: int) -> list:
    if interval not in ("1d",):
        raise MarketDataError("stooq supports daily intervals only")
    ticker = symbol.replace("-", "").replace("/", "")
    params = {"s": ticker, "i": "d"}
    try:
        response = httpx.get(
            STOOQ_URL, params=params, timeout=REQUEST_TIMEOUT, headers={"user-agent": USER_AGENT}
        )
        response.raise_for_status()
        text = response.text.strip()
    except (httpx.HTTPError, ValueError) as error:
        raise MarketDataError(f"stooq failed for {symbol}: {error}") from error

    if not text or text.startswith("No symbol"):
        raise MarketDataError(f"stooq returned no data for {symbol}")

    lines = text.splitlines()
    if len(lines) < 2:
        raise MarketDataError(f"stooq returned no usable bars for {symbol}")

    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            rows.append(
                {
                    "timestamp": parts[0],
                    "open": float(parts[1]),
                    "high": float(parts[2]),
                    "low": float(parts[3]),
                    "close": float(parts[4]),
                    "volume": float(parts[5]) if len(parts) > 5 and parts[5] else 0.0,
                }
            )
        except (ValueError, IndexError):
            continue
    if not rows:
        raise MarketDataError(f"stooq returned no usable bars for {symbol} at {interval}")
    return rows[-limit:]


def fetch_candles(
    symbol: str,
    interval: str = "1h",
    limit: int = 400,
    *,
    use_cache: bool = True,
) -> Candles:
    """Return the most recent `limit` validated candles for `symbol`."""
    if limit < 16:
        raise MarketDataError("limit must be at least 16")
    if interval not in INTERVALS:
        raise ValueError(f"unsupported interval {interval!r}")

    key = (symbol.upper(), interval, str(limit))
    if use_cache:
        cached = _cache.get(key)
        if cached is not None:
            return cached

    failures: list[str] = []
    for source, fetcher in _sources_for(symbol):
        try:
            candles = build_candles(fetcher(symbol, interval, limit))
        except MarketDataError as error:
            failures.append(str(error))
            continue
        except ValueError as error:
            failures.append(f"{source}: invalid bars ({error})")
            continue
        if use_cache:
            _cache.put(key, candles)
        return candles

    raise MarketDataError(
        f"no provider could supply {symbol!r} at {interval}: " + " | ".join(failures)
    )