"""
Solana whale pipeline API — Helius webhook receiver, tracked-whale management,
webhook registration, safety dry-run, and status. Signals flow into the
existing signal/auto-execute pipeline (paper/demo/live via trade gate).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.device_auth import require_device_id
from app.models import DeviceSettings
from app.services.solana_whale_service import (
    evaluate_strategy,
    get_device_whales,
    get_token_context,
    handle_whale_event,
    last_events,
    parse_helius_webhook,
    register_helius_webhook,
    tracked_whales,
)

router = APIRouter(prefix="/solana/whales", tags=["solana-whales"])


def _device_id_dep(x_device_id: Optional[str] = Header(None, alias="X-Device-ID")) -> str:
    return require_device_id(x_device_id)


class WhaleAddRequest(BaseModel):
    wallet: str


class EvaluateRequest(BaseModel):
    mint: str
    whale_sol_spent: float = 5.0


@router.post("/webhook")
async def helius_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Helius enhanced webhook receiver. Dispatches to every device that has
    auto-execute enabled; per-device whale lists are matched inside."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid JSON")

    events = parse_helius_webhook(payload)
    if not events:
        return {"received": 0}

    res = await db.execute(select(DeviceSettings))
    results = []
    for row in res.scalars().all():
        wallets = await get_device_whales(db, row.device_id)
        for ev in events:
            if wallets and ev.get("whale") and ev["whale"] not in wallets:
                continue
            try:
                out = await handle_whale_event(db, row.device_id, ev)
                results.append({"device": row.device_id, "mint": ev["mint"], "result": out.get("filtered") and "filtered" or "dispatched"})
            except Exception as e:  # noqa: BLE001
                results.append({"device": row.device_id, "mint": ev["mint"], "error": str(e)[:120]})
    await db.commit()
    return {"received": len(events), "dispatched": results}


@router.get("")
async def list_whales(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return {"env_whales": tracked_whales(), "device_whales": await get_device_whales(db, device_id)}


@router.post("")
async def add_whale(
    req: WhaleAddRequest,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    wallet = req.wallet.strip()
    if not wallet or len(wallet) < 32:
        raise HTTPException(status_code=400, detail="invalid Solana wallet address")
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if row is None:
        row = DeviceSettings(device_id=device_id)
        db.add(row)
    prefs = json.loads(row.preferences) if row.preferences else {}
    wallets = list(prefs.get("tracked_whales", []))
    if wallet not in wallets:
        wallets.append(wallet)
    prefs["tracked_whales"] = wallets
    row.preferences = json.dumps(prefs)
    await db.commit()
    return {"success": True, "tracked_whales": wallets}


@router.delete("/{wallet}")
async def remove_whale(
    wallet: str,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if row and row.preferences:
        prefs = json.loads(row.preferences)
        prefs["tracked_whales"] = [w for w in prefs.get("tracked_whales", []) if w != wallet]
        row.preferences = json.dumps(prefs)
        await db.commit()
    return {"success": True}


@router.post("/register-webhook")
async def register_webhook(
    webhook_url: str,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    wallets = await get_device_whales(db, device_id)
    return await register_helius_webhook(webhook_url, wallets)


@router.post("/evaluate")
async def evaluate_mint(req: EvaluateRequest):
    """Dry-run the Birdeye + RugCheck safety filters for a mint (no trade)."""
    async with httpx.AsyncClient(timeout=12.0) as client:
        ctx = await get_token_context(client, req.mint)
    verdict = evaluate_strategy(ctx, req.whale_sol_spent)
    return {"mint": req.mint, "context": ctx, "verdict": verdict}


@router.get("/top")
async def top_whales(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    """View top whales to watch: curated seed list + currently tracked +
    whale wallets seen in recent events. Users add any of them with one call."""
    seed = []
    if settings.HELIUS_TOP_WHALES:
        seed = [w.strip() for w in settings.HELIUS_TOP_WHALES.split(",") if w.strip()]
    tracked = await get_device_whales(db, device_id)
    seen = []
    for ev in last_events(100):
        w = ev.get("whale")
        if w and w not in seen and w not in tracked and w not in seed:
            seen.append(w)
    return {
        "suggested": seed,
        "tracked": tracked,
        "seen_recently": seen,
        "last_events": last_events(10),
    }


@router.get("/status")
async def whale_status(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return {
        "helius_configured": bool(settings.HELIUS_API_KEY),
        "birdeye_configured": bool(settings.BIRDEYE_API_KEY),
        "tracked_whales": await get_device_whales(db, device_id),
        "thresholds": {
            "min_whale_sol": settings.SOLANA_WHALE_MIN_SOL,
            "min_liquidity_usd": settings.SOLANA_MIN_LIQUIDITY_USD,
            "max_risk_score": settings.SOLANA_MAX_RISK_SCORE,
        },
        "last_events": last_events(),
    }
