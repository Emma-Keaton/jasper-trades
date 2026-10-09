"""Dex chain watcher API — hot tokens, top performers, whales, spikes per chain."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services.dex_chain_watch import (
    build_signal_records,
    ensure_fresh,
    refresh_snapshots,
    snapshot,
)

router = APIRouter()


@router.get("/dex-chains/snapshot")
async def get_snapshot() -> Dict[str, Any]:
    return await ensure_fresh()


@router.post("/dex-chains/refresh")
async def post_refresh() -> Dict[str, Any]:
    return await refresh_snapshots()


@router.get("/dex-chains/hot-tokens")
async def hot_tokens(chain: Optional[str] = Query(None)) -> Dict[str, Any]:
    snap = await ensure_fresh()
    chains = [chain] if chain else list(snap["per_chain"].keys())
    return {"chains": chains, "items": {c: snap["per_chain"].get(c, {}).get("hot_tokens", []) for c in chains}}


@router.get("/dex-chains/top-performers")
async def top_performers(chain: Optional[str] = Query(None)) -> Dict[str, Any]:
    snap = await ensure_fresh()
    chains = [chain] if chain else list(snap["per_chain"].keys())
    return {"chains": chains, "items": {c: snap["per_chain"].get(c, {}).get("top_performers", []) for c in chains}}


@router.get("/dex-chains/whales")
async def whales(chain: Optional[str] = Query(None)) -> Dict[str, Any]:
    snap = await ensure_fresh()
    chains = [chain] if chain else list(snap["per_chain"].keys())
    return {"chains": chains, "items": {c: snap["per_chain"].get(c, {}).get("whales", []) for c in chains}}


@router.get("/dex-chains/spikes")
async def spikes(chain: Optional[str] = Query(None)) -> Dict[str, Any]:
    snap = await ensure_fresh()
    chains = [chain] if chain else list(snap["per_chain"].keys())
    return {"chains": chains, "items": {c: snap["per_chain"].get(c, {}).get("spikes", []) for c in chains}}


@router.get("/dex-chains/signal-records")
async def signal_records() -> Dict[str, Any]:
    """Flattened autotrade candidates from the current watcher snapshot."""
    snap = await ensure_fresh()
    out: Dict[str, Any] = {}
    for chain, buckets in snap.get("per_chain", {}).items():
        out[chain] = {
            "hot_tokens": build_signal_records(buckets.get("hot_tokens", []), "dexwatch-hot"),
            "top_performers": build_signal_records(buckets.get("top_performers", []), "dexwatch-top"),
            "whales": build_signal_records(buckets.get("whales", []), "dexwatch-whale"),
            "spikes": build_signal_records(buckets.get("spikes", []), "dexwatch-spike"),
        }
    return out
