"""Dex chain watcher — hot tokens, top performers, whales, and spikes for both chains.

Mirrors the beast-trader dexwatch/whalewatch collectors in intent (Dexscreener
snapshots, classification into actionable buckets) but wired for Jasper's
Groq-backed signal pipeline.

Design rules (same as beast-trader):
- Pure parsing is separated from fetching so provider payload changes fail in
  tests, not as empty rows in production.
- Every fetch is budget/time bounded; a collector that throws would kill every
  tick. Failures degrade to "keep the previous snapshot".
- The watcher only *classifies*. It never trades on its own — execution is the
  autotrade executor's decision, fed by `build_signal_records`.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

DEX_BASE = "https://api.dexscreener.com"
DEFAULT_TIMEOUT_MS = 8000
SNAPSHOT_TTL_S = 120.0

WATCH_CHAINS = ["solana", "ethereum"]
MIN_POOL_LIQUIDITY_USD = {"solana": 100_000, "ethereum": 500_000}

# A "spike" is relative to the same pool's own recent history: volume and buy
# count in the 5m window must dominate the 1h rate by this factor.
SPIKE_VOLUME_FACTOR = 3.0
# A "whale" proxy: buys in 5m exceed this AND dominate sells by this factor.
WHALE_MIN_BUYS_5M = 40
WHALE_BUY_DOMINANCE = 3.0


# ---------------------------------------------------------------------------
# parsing (pure)
# ---------------------------------------------------------------------------

def _num(v: Any) -> Optional[float]:
    try:
        n = float(v)
        return n if n == n and n != float("inf") else None
    except (TypeError, ValueError):
        return None


def parse_pair(pair: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(pair, dict):
        return None
    base = pair.get("baseToken") or {}
    if not base.get("address"):
        return None
    price = _num(pair.get("priceUsd") or pair.get("priceNative"))
    if price is None or price <= 0:
        return None
    txns = pair.get("txns") or {}
    m5 = txns.get("m5") or {}
    h1 = txns.get("h1") or {}
    h24 = txns.get("h24") or {}

    def _sumw(key: str) -> Optional[float]:
        vals = [_num(w.get(key)) for w in (m5, h1, h24)]
        finite = [v for v in vals if v is not None]
        return sum(finite) if finite else None

    return {
        "symbol": str(base.get("symbol") or "").upper(),
        "address": base.get("address"),
        "chain": pair.get("chainId"),
        "dex_id": pair.get("dexId"),
        "pair_address": pair.get("pairAddress"),
        "price_usd": price,
        "liquidity_usd": _num((pair.get("liquidity") or {}).get("usd")),
        "volume_usd": _num((pair.get("volume") or {}).get("h24")),
        "volume_5m": _num((pair.get("volume") or {}).get("m5")),
        "price_change_5m": _num((pair.get("priceChange") or {}).get("m5")),
        "price_change_1h": _num((pair.get("priceChange") or {}).get("h1")),
        "price_change_24h": _num((pair.get("priceChange") or {}).get("h24")),
        "buys": _sumw("buys"),
        "sells": _sumw("sells"),
        "buys_5m": _num(m5.get("buys")),
        "sells_5m": _num(m5.get("sells")),
        "buys_1h": _num(h1.get("buys")),
        "sells_1h": _num(h1.get("sells")),
        "source": "dexscreener",
    }


def parse_pairs_response(json: Dict[str, Any], chains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    pairs = json.get("pairs") if isinstance(json, dict) else None
    if not isinstance(pairs, list):
        return []
    out: List[Dict[str, Any]] = []
    for p in pairs:
        row = parse_pair(p)
        if not row:
            continue
        if chains and row.get("chain") not in chains:
            continue
        out.append(row)
    return out


def rank_by_liquidity_complete_first(rows: List[Dict[str, Any]], limit: int = 30, min_liquidity: float = 0.0) -> List[Dict[str, Any]]:
    by_token: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        liq = r.get("liquidity_usd")
        if liq is None or liq < min_liquidity:
            continue
        prev = by_token.get(r["address"])
        r_complete = r.get("price_change_1h") is not None
        prev_complete = prev is not None and prev.get("price_change_1h") is not None
        if prev is None or (r_complete and not prev_complete) or (r_complete == prev_complete and liq > prev.get("liquidity_usd", 0)):
            by_token[r["address"]] = r
    return sorted(
        by_token.values(),
        key=lambda r: (r.get("price_change_1h") is not None, r.get("liquidity_usd") or 0),
        reverse=True,
    )[:limit]


# ---------------------------------------------------------------------------
# classification (pure)
# ---------------------------------------------------------------------------

def classify_rows(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    hot: List[Dict[str, Any]] = []
    performers: List[Dict[str, Any]] = []
    whales: List[Dict[str, Any]] = []
    spikes: List[Dict[str, Any]] = []

    for r in rows:
        liq = r.get("liquidity_usd") or 0
        vol5 = r.get("volume_5m")
        vol1h_per5m = (r.get("volume_usd") or 0) / (24 * 12)  # rough 5m baseline from 24h
        chg24 = r.get("price_change_24h")
        chg1h = r.get("price_change_1h")
        b5 = r.get("buys_5m") or 0
        s5 = r.get("sells_5m") or 0

        # Hot: meaningful 5m turnover on a pool we could trade
        if liq >= 50_000 and (vol5 or 0) > 25_000:
            hot.append(r)

        # Top performers: strong 24h gain with real liquidity
        if liq >= 100_000 and chg24 is not None and chg24 > 10:
            performers.append(r)

        # Spike: 5m volume/tx dominates the pool's own baseline
        if vol5 and vol1h_per5m and vol5 > SPIKE_VOLUME_FACTOR * vol1h_per5m and b5 + s5 >= 20:
            spikes.append(r)

        # Whale proxy: one-sided aggressive buying on a pool big enough to matter
        if liq >= 250_000 and b5 >= WHALE_MIN_BUYS_5M and s5 > 0 and b5 > WHALE_BUY_DOMINANCE * s5:
            whales.append(r)

    by_vol = sorted(hot, key=lambda r: r.get("volume_5m") or 0, reverse=True)
    by_perf = sorted(performers, key=lambda r: r.get("price_change_24h") or 0, reverse=True)
    by_whale = sorted(whales, key=lambda r: r.get("buys_5m") or 0, reverse=True)
    by_spike = sorted(spikes, key=lambda r: r.get("volume_5m") or 0, reverse=True)
    return {"hot_tokens": by_vol[:20], "top_performers": by_perf[:20], "whales": by_whale[:20], "spikes": by_spike[:20]}


# ---------------------------------------------------------------------------
# service state
# ---------------------------------------------------------------------------

@dataclass
class _State:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: float = 0.0
    per_chain: Dict[str, Dict[str, List[Dict[str, Any]]]] = field(default_factory=dict)


_state = _State()
_lock = asyncio.Lock()


async def _fetch_chain(chain: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    queries = {
        "solana": ["SOL/USDC", "BONK/SOL", "WIF/SOL"],
        "ethereum": ["ETH/USDC", "WETH/USDC", "cbETH/ETH"],
    }.get(chain, [f"{chain.upper()}/USDC"])
    out: List[Dict[str, Any]] = []
    for q in queries:
        try:
            r = await client.get(f"{DEX_BASE}/latest/dex/search", params={"q": q}, headers={"accept": "application/json"})
            if r.status_code != 200:
                continue
            out.extend(parse_pairs_response(r.json(), chains=[chain]))
        except Exception as e:
            logger.warning("dexchain search failed", chain=chain, query=q, error=str(e)[:120])
    return rank_by_liquidity_complete_first(out, limit=30, min_liquidity=MIN_POOL_LIQUIDITY_USD.get(chain, 20_000))


async def refresh_snapshots() -> Dict[str, Any]:
    """Fetch both chains and rebuild the classification cache."""
    async with _lock:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_MS / 1000) as client:
                sol, eth = await asyncio.gather(_fetch_chain("solana", client), _fetch_chain("ethereum", client))
        except Exception as e:
            logger.error("dexchain refresh failed", error=str(e)[:200])
            return snapshot()

        rows = sol + eth
        _state.rows = rows
        _state.fetched_at = time.time()
        _state.per_chain = {
            "solana": classify_rows(sol),
            "ethereum": classify_rows(eth),
        }
        logger.info("dexchain snapshot refreshed", solana=len(sol), ethereum=len(eth))
        return snapshot()


def snapshot() -> Dict[str, Any]:
    return {
        "fetched_at": _state.fetched_at,
        "age_s": round(time.time() - _state.fetched_at, 1) if _state.fetched_at else None,
        "chains": list(_state.per_chain.keys()),
        "total_rows": len(_state.rows),
        "per_chain": _state.per_chain,
    }


async def ensure_fresh() -> Dict[str, Any]:
    if time.time() - _state.fetched_at > SNAPSHOT_TTL_S or not _state.rows:
        return await refresh_snapshots()
    return snapshot()


def build_signal_records(rows: List[Dict[str, Any]], source_tag: str) -> List[Dict[str, Any]]:
    """Turn classified watcher rows into SignalTip-shaped records for autotrade.

    These flow through the same confidence-gated auto-executor as Telegram
    tips, so risk caps and the kill-switch apply identically.
    """
    out: List[Dict[str, Any]] = []
    for r in rows[:10]:
        out.append({
            "symbol": r["symbol"],
            "side": "long",
            "timeframe": "5m",
            "confidence": 0.65,
            "rationale": f"{source_tag} ({r.get('chain')}): volume ${int(r.get('volume_5m') or 0):,} 5m, change 24h {r.get('price_change_24h')}%",
            "source": source_tag,
            "price_usd": r.get("price_usd"),
            "address": r.get("address"),
            "chain": r.get("chain"),
        })
    return out
