"""Auto-trade loop for the DEX chain watchers.

Consumes classified DexScreener snapshots and routes the highest-conviction
buckets (spikes, whales, top performers) through the same SignalTip auto-exec
pipeline Telegram signals use, so paper-trading risk gates apply identically
and every trade is attributable to a watcher bucket.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from app.database import async_session
from app.models import DeviceSettings, SignalSource, SignalTip
from app.services.dex_chain_watch import build_signal_records, refresh_snapshots, snapshot
from app.services.signal_sources.ingest import (
    DEFAULT_MIN_CONFIDENCE,
    execute_signal,
    get_signal_settings,
)

logger = structlog.get_logger(__name__)

AUTOTRADE_MIN_CONFIDENCE = 0.70
AUTOTRADE_MAX_RECORDS_PER_TICK = 6


async def _ensure_dexwatch_source(db, device_id: str) -> SignalSource:
    res = await db.execute(
        select(SignalSource).where(
            SignalSource.device_id == device_id,
            SignalSource.source_type == "dexwatch",
        )
    )
    row = res.scalar_one_or_none()
    if row:
        return row
    row = SignalSource(
        device_id=device_id,
        source_type="dexwatch",
        display_name="Dex Chain Watcher",
        config={},
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _autotrade_device(db, device_id: str) -> Dict[str, Any]:
    settings = await get_signal_settings(db, device_id)
    if not settings.auto_execute_enabled:
        return {"device_id": device_id, "skipped": "auto_execute disabled"}

    snap = snapshot()
    records: List[Dict[str, Any]] = []
    for buckets in snap.get("per_chain", {}).values():
        records.extend(build_signal_records(buckets.get("spikes", []), "dexwatch-spike"))
        records.extend(build_signal_records(buckets.get("whales", []), "dexwatch-whale"))
        records.extend(build_signal_records(buckets.get("top_performers", []), "dexwatch-top"))

    # Highest conviction first, deduped by slug
    records.sort(key=lambda r: r.get("confidence") or 0, reverse=True)
    seen = set()
    picked = []
    for r in records:
        slug = f"{r['symbol']}-{r['side']}"
        if slug in seen:
            continue
        seen.add(slug)
        picked.append(r)
        if len(picked) >= AUTOTRADE_MAX_RECORDS_PER_TICK:
            break

    src = await _ensure_dexwatch_source(db, device_id)
    executed = 0
    for r in picked:
        if (r.get("confidence") or 0) < max(settings.min_confidence, AUTOTRADE_MIN_CONFIDENCE):
            continue
        tip_dict = {
            "source_id": str(src.id),
            "slug": f"{r['symbol']}-{r['side']}",
            "symbol": r["symbol"],
            "side": r["side"],
            "timeframe": r.get("timeframe"),
            "confidence": r["confidence"],
            "rationale": r.get("rationale"),
            "text": r.get("rationale"),
            "url": None,
        }
        try:
            from app.services.signal_sources.ingest import ingest_tip_dict
            tip = await ingest_tip_dict(db, device_id, tip_dict)
            if tip is None:
                continue
            result = await execute_signal(db, device_id, tip)
            if result.get("error") is None:
                executed += 1
        except Exception as e:
            logger.warning("dexwatch autotrade failed", device_id=device_id, symbol=r["symbol"], error=str(e)[:200])
    await db.commit()
    return {"device_id": device_id, "candidates": len(picked), "executed": executed}


async def dexchain_autotrade_tick() -> Dict[str, Any]:
    await refresh_snapshots()
    out: List[Dict[str, Any]] = []
    async with async_session() as db:
        res = await db.execute(select(DeviceSettings))
        for row in res.scalars().all():
            try:
                out.append(await _autotrade_device(db, row.device_id))
            except Exception as e:
                logger.warning("dexchain autotrade device failed", device_id=row.device_id, error=str(e)[:200])
    return {"devices": out}


async def start_dexchain_watch(poll_s: int = 60) -> None:
    """Background loop: refresh snapshots + autotrade tick every `poll_s` seconds."""
    while True:
        try:
            await dexchain_autotrade_tick()
        except Exception as e:
            logger.error("dexchain watcher tick failed", error=str(e)[:200])
        await asyncio.sleep(poll_s)
