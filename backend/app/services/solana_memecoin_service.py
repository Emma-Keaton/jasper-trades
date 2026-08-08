"""
Solana Memecoin Market Data - DexScreener discovery + Jupiter pricing.

The base Solana broker (app/brokers/solana_service.py) only knows ~7 hardcoded
mints. This service adds dynamic memecoin discovery + market polling for ANY
SPL token on Solana using the public DexScreener API (Nigeria-accessible,
no auth, 60 req/min). Execution stays on Jupiter (via solana_service.py), but
this service resolves an arbitrary ticker -> mint address, then polls live
price/liquidity/volume so the AI can trade real memecoins.

Endpoints used (verified):
  GET https://api.dexscreener.com/latest/dex/search?q=<query>
  GET https://api.dexscreener.com/token-pairs/v1/solana/<mint>
  GET https://api.dexscreener.com/tokens/v1/solana/<mint(s)>
  GET https://api.dexscreener.com/metas/trending/v1
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

SOLANA_CHAIN_ID = "solana"


class SolanaMemecoinDataService:
    """DexScreener-based Solana memecoin discovery + market data."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.DEXSCREENER_API
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: float = 30.0

    async def search_tokens(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Solana tokens by symbol/name (memecoin discovery)."""
        url = f"{self.base_url}/latest/dex/search"
        params = {"q": query}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        pairs = payload.get("pairs") or []
        sol_pairs = [p for p in pairs if p.get("chainId") == SOLANA_CHAIN_ID]
        results: List[Dict[str, Any]] = []
        seen_mints: set[str] = set()
        for p in sorted(
            sol_pairs,
            key=lambda x: float(x.get("liquidity", {}).get("usd") or 0),
            reverse=True,
        ):
            base = p.get("baseToken") or {}
            mint = base.get("address")
            if not mint or mint in seen_mints:
                continue
            seen_mints.add(mint)
            results.append(self._pair_to_market(p))
            if len(results) >= limit:
                break
        return results

    async def trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return trending Solana memecoins from DexScreener metas."""
        url = f"{self.base_url}/metas/trending/v1"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            metas = resp.json() or []
        out: List[Dict[str, Any]] = []
        for m in metas[:limit]:
            out.append(
                {
                    "slug": m.get("slug"),
                    "name": m.get("name"),
                    "description": m.get("description"),
                    "market_cap": m.get("marketCap"),
                    "liquidity": m.get("liquidity"),
                    "volume_24h": m.get("volume"),
                    "market_cap_change_24h": m.get("marketCapChange", {}).get("h24"),
                }
            )
        return out

    async def get_market(self, mint: str) -> Optional[Dict[str, Any]]:
        """Get the most liquid pair data for a token mint (cached)."""
        cached = self._cache.get(mint)
        if cached and time.time() - cached.get("ts", 0) < self._cache_ttl:
            return cached["data"]

        url = f"{self.base_url}/token-pairs/v1/{SOLANA_CHAIN_ID}/{mint}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        pairs = payload if isinstance(payload, list) else payload.get("pairs") or []
        if not pairs:
            return None

        best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd") or 0))
        data = self._pair_to_market(best)
        self._cache[mint] = {"ts": time.time(), "data": data}
        return data

    async def get_prices(self, mints: List[str]) -> Dict[str, float]:
        """Bulk price fetch keyed by mint."""
        result: Dict[str, float] = {}
        for mint in mints:
            m = await self.get_market(mint)
            if m and m.get("price_usd") is not None:
                result[mint] = float(m["price_usd"])
        return result

    @staticmethod
    def _pair_to_market(p: Dict[str, Any]) -> Dict[str, Any]:
        base = p.get("baseToken") or {}
        quote = p.get("quoteToken") or {}
        return {
            "chain_id": p.get("chainId"),
            "pair_address": p.get("pairAddress"),
            "dex": p.get("dexId"),
            "pair_url": p.get("url"),
            "base_mint": base.get("address"),
            "base_symbol": base.get("symbol"),
            "base_name": base.get("name"),
            "quote_symbol": quote.get("symbol"),
            "price_usd": float(p.get("priceUsd") or 0),
            "price_native": p.get("priceNative"),
            "liquidity_usd": float((p.get("liquidity") or {}).get("usd") or 0),
            "volume_24h": float((p.get("volume") or {}).get("h24") or 0),
            "market_cap": float(p.get("marketCap") or 0),
            "fdv": float(p.get("fdv") or 0),
            "price_change_5m": float((p.get("priceChange") or {}).get("m5") or 0),
            "price_change_1h": float((p.get("priceChange") or {}).get("h1") or 0),
            "price_change_24h": float((p.get("priceChange") or {}).get("h24") or 0),
            "txns_24h_buys": int((p.get("txns") or {}).get("h24", {}).get("buys") or 0),
            "txns_24h_sells": int((p.get("txns") or {}).get("h24", {}).get("sells") or 0),
            "pair_created_at": p.get("pairCreatedAt"),
        }

    def clear_cache(self) -> None:
        self._cache.clear()


_memecoin: Optional[SolanaMemecoinDataService] = None


def get_memecoin_service() -> SolanaMemecoinDataService:
    global _memecoin
    if _memecoin is None:
        _memecoin = SolanaMemecoinDataService()
    return _memecoin

