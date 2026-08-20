"""
CoinMarketCap market data service (optional provider).

Backs the market-data chain with top-cryptocurrency listings, 24h gainers /
losers, and USD price conversion. Wrapped the same way as the other providers:
methods never raise and return {"success": bool, ...} so the market-data router
can fail over to the next provider.

Configure with CMC_API_KEY (pro-api.coinmarketcap.com). A demo key is only
used against the *sandbox* API for local/dev sanity checks; production calls
always come from the configured key.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

CMC_PRO_BASE = "https://pro-api.coinmarketcap.com/v1"
CMC_SANDBOX_BASE = "https://sandbox-api.coinmarketcap.com/v1"
CMC_DEMO_KEY = "b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c"

# Map common symbols to CMC slugs (id lookup is more reliable, but symbol search
# keeps this dependency-free for arbitrary tickers).
_CMC_SLUGS = {
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
    "POL": "polygon-ecosystem-token",
    "AVAX": "avalanche-2",
    "LTC": "litecoin",
    "SHIB": "shiba-inu",
    "BONK": "bonk",
    "JUP": "jupiter-exchange-solana",
    "RAY": "raydium",
}


def _strip_pairs(symbol: str) -> str:
    s = symbol.replace("/", "").split(":")[0].upper()
    for d in ("USDT", "USDC", "USD", "BUSD"):
        if s.endswith(d) and len(s) > len(d):
            return s[: -len(d)]
    return s


class CoinMarketCapService:
    """Thin, failure-tolerant wrapper around the CMC API."""

    def __init__(self) -> None:
        self._api_key: Optional[str] = None
        self._base_url: str = CMC_PRO_BASE
        if settings.CMC_API_KEY:
            self._api_key = settings.CMC_API_KEY
            self._base_url = CMC_PRO_BASE
        elif settings.ENVIRONMENT != "production":
            # Demo key only for dev/sandbox sanity checks.
            self._api_key = CMC_DEMO_KEY
            self._base_url = CMC_SANDBOX_BASE

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> Dict[str, str]:
        return {"X-CMC_PRO_API_KEY": self._api_key or "", "Accept": "application/json"}

    async def _get(self, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.configured:
            return None
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{self._base_url}{path}", params=params, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.debug("CoinMarketCap request failed", path=path, error=str(e))
            return None

    async def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """USD price for a symbol via /tools/price-conversion."""
        data = await self._get(
            "/tools/price-conversion",
            {"symbol": _strip_pairs(symbol), "amount": "1", "convert": "USD"},
        )
        if not data or not data.get("data"):
            return None
        quote = (data["data"].get("quote") or {}).get("USD") or {}
        price = quote.get("price")
        if price is None:
            return None
        return {
            "symbol": symbol,
            "price": float(price),
            "market_cap": (quote.get("market_cap") or 0),
            "volume_24h": (quote.get("volume_24h") or 0),
            "price_change_24h": (quote.get("percent_change_24h") or 0),
            "provider": "coinmarketcap",
        }

    async def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Bulk quotes for a list of symbols (single-request best effort)."""
        try:
            ids = ",".join(_strip_pairs(s).lower() for s in symbols)
        except Exception:  # noqa: BLE001
            return {"success": False, "error": "invalid symbols"}
        data = await self._get(
            "/cryptocurrency/quotes/latest", {"slug": ids, "convert": "USD"}
        )
        if not data or not data.get("data"):
            return {"success": False, "error": "no data"}
        out: Dict[str, Any] = {}
        for _id, coin in data["data"].items():
            q = (coin.get("quote") or {}).get("USD") or {}
            out[coin.get("symbol", "").upper()] = {
                "name": coin.get("name"),
                "price_usd": q.get("price"),
                "market_cap": q.get("market_cap"),
                "volume_24h": q.get("volume_24h"),
                "price_change_24h": q.get("percent_change_24h"),
            }
        return {"success": True, "data": out, "provider": "coinmarketcap"}

    async def get_trending(self, limit: int = 10) -> Dict[str, Any]:
        """Trending gainers/losers over 24h."""
        data = await self._get(
            "/cryptocurrency/trending/gainers-losers/latest", {"limit": str(min(limit, 100))}
        )
        if not data:
            return {"success": False, "error": "no data"}
        raw = data.get("data") or {}

        def _fmt(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return [
                {
                    "symbol": (i.get("symbol") or "").upper(),
                    "name": i.get("name") or i.get("symbol") or "",
                    "price_usd": (i.get("quote") or {}).get("USD", {}).get("price"),
                    "change_24h": (i.get("quote") or {}).get("USD", {}).get("percent_change_24h"),
                    "market_cap": (i.get("quote") or {}).get("USD", {}).get("market_cap"),
                }
                for i in (raw.get("gainers") or [])[:limit]
            ]

        return {
            "success": True,
            "data": {
                "trending": _fmt(raw.get("gainers") or []),
                "gainers": _fmt(raw.get("gainers") or []),
                "losers": _fmt(raw.get("losers") or []),
            },
            "provider": "coinmarketcap",
        }

    async def get_listings(self, limit: int = 20) -> Dict[str, Any]:
        """Top cryptocurrencies by market cap."""
        data = await self._get(
            "/cryptocurrency/listings/latest",
            {"start": "1", "limit": str(min(limit, 100)), "convert": "USD"},
        )
        if not data or not data.get("data"):
            return {"success": False, "error": "no data"}
        out = []
        for coin in data["data"]:
            q = (coin.get("quote") or {}).get("USD") or {}
            out.append(
                {
                    "symbol": coin.get("symbol", "").upper(),
                    "name": coin.get("name"),
                    "price_usd": q.get("price"),
                    "market_cap": q.get("market_cap"),
                    "volume_24h": q.get("volume_24h"),
                    "price_change_24h": q.get("percent_change_24h"),
                }
            )
        return {"success": True, "data": out, "provider": "coinmarketcap"}

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": "coinmarketcap",
            "base_url": self._base_url,
        }


_cmc: Optional[CoinMarketCapService] = None


def get_coinmarketcap_service() -> CoinMarketCapService:
    global _cmc
    if _cmc is None:
        _cmc = CoinMarketCapService()
    return _cmc