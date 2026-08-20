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
  GET https://api.dexscreener.com/token-profiles/latest/v1   (newly launched tokens)
  GET https://api-v3.raydium.io/pools/info/mint?mint1=<mint> (Raydium pool data)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

SOLANA_CHAIN_ID = "solana"
RAYDIUM_API = "https://api-v3.raydium.io"


class SolanaMemecoinDataService:
    """DexScreener-based Solana memecoin discovery + market data."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.DEXSCREENER_API
        self.raydium_base = RAYDIUM_API
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

    # ------------------------------------------------------------------
    # Raydium v3 (on-chain pool data; supplements DexScreener)
    # ------------------------------------------------------------------

    async def get_raydium_pool(self, mint: str) -> Optional[Dict[str, Any]]:
        """Best Raydium pool for a mint (price/liquidity/24h volume)."""
        url = f"{self.raydium_base}/pools/info/mint"
        params = {"mint1": mint}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.debug("Raydium pool fetch failed", error=str(e))
            return None
        for pool in payload.get("data") or []:
            quote = pool.get("quote") or {}
            base_info = (pool.get("mintA") or {}).get("info") or {}
            quote_info = (pool.get("mintB") or {}).get("info") or {}
            return {
                "base_mint": (pool.get("mintA") or {}).get("mint"),
                "base_symbol": base_info.get("symbol"),
                "quote_symbol": quote_info.get("symbol") or "SOL",
                "price_usd": quote.get("price", 0),
                "price_native": quote.get("price", 0),
                "liquidity_usd": float(quote.get("liquidity", 0) or 0),
                "volume_24h": float(quote.get("volume24h", 0) or 0),
                "price_change_24h": quote.get("priceChange24h", 0),
                "source": "raydium",
            }
        return None

    async def _raydium_top_pools(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top Solana pools by 24h volume from the Raydium daily-pools endpoint."""
        url = f"{self.raydium_base}/pools/day"
        try:
            params = {"page": "1", "pageSize": str(limit), "orderby": "volume24h", "descending": "true"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.debug("Raydium daily pools failed", error=str(e))
            return []
        out: List[Dict[str, Any]] = []
        for pool in payload.get("data") or []:
            out.append(
                {
                    "base_mint": (pool.get("mintA") or {}).get("mint"),
                    "base_symbol": (pool.get("mintA") or {}).get("info", {}).get("symbol"),
                    "base_name": (pool.get("mintA") or {}).get("info", {}).get("name"),
                    "price_usd": (pool.get("quote") or {}).get("price", 0),
                    "volume_24h": float((pool.get("quote") or {}).get("volume24h", 0) or 0),
                    "liquidity_usd": float((pool.get("quote") or {}).get("liquidity", 0) or 0),
                    "price_change_24h": (pool.get("quote") or {}).get("priceChange24h", 0),
                    "source": "raydium",
                }
            )
        return out

    # ------------------------------------------------------------------
    # Discover (newly launched tokens) vs trending (high 24h volume)
    # ------------------------------------------------------------------

    async def discover(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Newly launched/promoted Solana tokens (newest first, low cap)."""
        url = f"{self.base_url}/token-profiles/latest/v1"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                profiles = resp.json() or []
        except Exception as e:  # noqa: BLE001
            logger.debug("DexScreener token-profiles fetch failed", error=str(e))
            profiles = []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for p in profiles[:max(limit * 2, 20)]:
            token = (p.get("tokenProfile") or {}).get("tokens") or [{}]
            t = token[0]
            mint = t.get("address")
            if not mint or mint in seen:
                continue
            seen.add(mint)
            out.append(
                {
                    "chain_id": SOLANA_CHAIN_ID,
                    "base_mint": mint,
                    "base_symbol": (t.get("symbol") or "").upper(),
                    "base_name": t.get("name"),
                    "liquidity_usd": float(((p.get("tokenProfile") or {}).get("liquidityList") or [{}])[0].get("liquidity", 0) or 0),
                    "volume_24h": 0.0,
                    "market_cap": float(((p.get("tokenProfile") or {}).get("marketCapList") or [{}])[0].get("marketCap", 0) or 0),
                    "price_usd": float(((p.get("tokenProfile") or {}).get("priceList") or [{}])[0].get("price", 0) or 0),
                    "pair_created_at": p.get("createTime"),
                    "is_new": True,
                }
            )
            if len(out) >= limit:
                break
        return out

    async def trending_v2(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Merged trending feed: high 24h volume Raydium pools + DexScreener metas.

        Dedupes by mint and prefers the higher-liquidity entry.
        """
        merged: Dict[str, Dict[str, Any]] = {}
        for item in await self._raydium_top_pools(limit):
            mint = item.get("base_mint")
            if mint:
                merged[mint] = item
        try:
            for item in await self.trending(limit):
                merged.setdefault(item.get("base_mint") or item.get("slug") or "", item)
        except Exception:  # noqa: BLE001
            pass
        ranked = sorted(
            merged.values(),
            key=lambda x: float(x.get("volume_24h") or 0) * 1.0
            + float(x.get("liquidity_usd") or 0) * 0.1,
            reverse=True,
        )
        return ranked[:limit]

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

