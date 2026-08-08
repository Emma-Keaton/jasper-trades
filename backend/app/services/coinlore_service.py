"""
CoinLore Market Data - free fallback crypto price provider.

Used as the LAST-RESORT fallback in the market-data priority chain:
    CoinGecko (default) -> CCXT (Bybit/Binance) -> CoinLore (fallback).

CoinLore is a free, no-auth, globally-accessible crypto API (Nigeria-safe).
Endpoints:
    GET https://api.coinlore.net/api/ticker/?symbol=BTC,ETH  (price by symbol)
    GET https://api.coinlore.net/api/tickers/                 (top 100)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

COINLORE_API = "https://api.coinlore.net"


class CoinLoreService:
    """CoinLore fallback price provider."""

    async def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get last USD price for a crypto symbol (e.g. 'BTC', 'ETH')."""
        clean = symbol.replace("/", "").split(":")[0].upper()
        # Extract base if it looks like a pair (BTCUSDT, BTC/USDT).
        for delim in ("USDT", "USD", "USDC"):
            if clean.endswith(delim) and len(clean) > len(delim):
                clean = clean[: -len(delim)]
                break
        url = f"{COINLORE_API}/api/ticker/"
        params = {"symbol": clean}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        if not data:
            return None
        row = data[0]
        price = float(row.get("price_usd") or row.get("price") or 0)
        return {
            "symbol": row.get("symbol", clean),
            "price": price,
            "provider": "coinlore",
            "rank": row.get("rank"),
        }


_coinlore: Optional[CoinLoreService] = None


def get_coinlore_service() -> CoinLoreService:
    global _coinlore
    if _coinlore is None:
        _coinlore = CoinLoreService()
    return _coinlore
