"""
Market Data Router - priority-chained crypto price lookup.

Priority (per project requirements):
  1. CoinGecko  (default) - free, no auth, Nigeria-safe
  2. CCXT       (secondary) - Bybit then Binance (probe-gated)
  3. CoinLore   (fallback) - free, no auth, Nigeria-safe

Fails over automatically down the chain so a single provider outage never
blocks pricing.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import structlog

from app.config import settings
from app.services.coinlore_service import get_coinlore_service

logger = structlog.get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"


def _symbol_to_coingecko_id(symbol: str) -> str:
    """Best-effort map of common symbols to CoinGecko IDs."""
    s = symbol.replace("/", "").split(":")[0].upper()
    for d in ("USDT", "USDC", "USD", "BUSD"):
        if s.endswith(d) and len(s) > len(d):
            s = s[: -len(d)]
            break
    return {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "LINK": "chainlink",
        "MATIC": "matic-network",
        "AVAX": "avalanche-2",
        "LTC": "litecoin",
        "SHIB": "shiba-inu",
        "BONK": "bonk",
        "JUP": "jupiter-exchange-solana",
    }.get(s, s.lower())


class MarketDataRouter:
    """Chained crypto price resolution: CoinGecko -> CCXT -> CoinLore."""

    async def get_price(self, symbol: str) -> Dict[str, Any]:
        providers = [
            ("coingecko", self._coingecko),
            ("ccxt", self._ccxt),
            ("coinlore", self._coinlore),
        ]
        for name, fn in providers:
            try:
                result = await fn(symbol)
                if result and result.get("price"):
                    result["provider"] = name
                    return result
            except Exception as e:  # noqa: BLE001
                logger.debug("Market-data provider failed", provider=name, error=str(e))
        return {"symbol": symbol, "price": 0.0, "provider": "none"}

    async def _coingecko(self, symbol: str) -> Optional[Dict[str, Any]]:
        cid = _symbol_to_coingecko_id(symbol)
        url = f"{COINGECKO_API}/simple/price"
        params = {"ids": cid, "vs_currencies": "usd"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        price = (data.get(cid, {}) or {}).get("usd")
        if price is None:
            return None
        return {"symbol": symbol, "price": float(price)}

    async def _ccxt(self, symbol: str) -> Optional[Dict[str, Any]]:
        from app.services.ccxt_market_data_service import get_ccxt_market_data_service

        result = await get_ccxt_market_data_service().get_price(symbol)
        if result.get("price"):
            return {"symbol": symbol, "price": float(result["price"])}
        return None

    async def _coinlore(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await get_coinlore_service().get_price(symbol)


_router: Optional[MarketDataRouter] = None


def get_market_data_router() -> MarketDataRouter:
    global _router
    if _router is None:
        _router = MarketDataRouter()
    return _router
