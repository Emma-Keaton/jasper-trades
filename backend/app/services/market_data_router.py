"""
Market Data Router - priority-chained crypto price lookup.

Priority (per project requirements):
  1. CoinGecko  (default) - free, no auth, Nigeria-safe
  2. CCXT       (secondary) - Bybit then Binance (probe-gated)
  3. CoinMarketCap (optional) - needs CMC_API_KEY
  4. CoinLore   (fallback) - free, no auth, Nigeria-safe

Fails over automatically down the chain so a single provider outage never
blocks pricing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import settings
from app.services.coinlore_service import get_coinlore_service
from app.services.coinmarketcap_service import get_coinmarketcap_service

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
    """Chained crypto price resolution: CoinGecko -> CCXT -> CoinMarketCap -> CoinLore."""

    async def get_price(self, symbol: str) -> Dict[str, Any]:
        providers = [
            ("coingecko", self._coingecko),
            ("ccxt", self._ccxt),
            ("coinmarketcap", self._coinmarketcap),
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

    async def _coinmarketcap(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await get_coinmarketcap_service().get_price(symbol)

    async def _coinlore(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await get_coinlore_service().get_price(symbol)

    # ------------------------------------------------------------------
    # Trending / gainers-losers (merged, multi-provider)
    # ------------------------------------------------------------------

    async def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Merged crypto trending feed: CoinGecko search + CMC gainers + memecoins."""
        merged: Dict[str, Dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{COINGECKO_API}/search/trending")
                resp.raise_for_status()
                items = (resp.json().get("items") or [])[:limit]
            for it in items:
                coin = it.get("item") or {}
                sym = (coin.get("symbol") or "").upper()
                if sym:
                    merged[sym] = {
                        "symbol": sym,
                        "name": coin.get("name") or sym,
                        "price_change_24h": None,
                        "source": "coingecko",
                    }
        except Exception as e:  # noqa: BLE001
            logger.debug("CoinGecko trending failed", error=str(e))

        cmc = await get_coinmarketcap_service()
        if cmc.configured:
            res = await cmc.get_trending(limit)
            if res.get("success"):
                for item in res["data"].get("gainers") or []:
                    sym = item.get("symbol")
                    if sym and sym not in merged:
                        merged[sym] = {
                            "symbol": sym,
                            "name": item.get("name") or sym,
                            "price_usd": item.get("price_usd"),
                            "price_change_24h": item.get("change_24h"),
                            "source": "coinmarketcap",
                        }

        try:
            from app.services.solana_memecoin_service import get_memecoin_service

            for item in await get_memecoin_service().trending_v2(limit):
                sym = (item.get("base_symbol") or item.get("slug") or "").upper()
                if sym and sym not in merged:
                    merged[sym] = {
                        "symbol": sym,
                        "name": item.get("base_name") or sym,
                        "price_usd": item.get("price_usd"),
                        "price_change_24h": item.get("price_change_24h"),
                        "source": item.get("source", "memecoin"),
                    }
        except Exception as e:  # noqa: BLE001
            logger.debug("Memecoin trending merge failed", error=str(e))

        return list(merged.values())[:limit]


_router: Optional[MarketDataRouter] = None


def get_market_data_router() -> MarketDataRouter:
    global _router
    if _router is None:
        _router = MarketDataRouter()
    return _router
