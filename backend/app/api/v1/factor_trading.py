"""
Factor Trading Results API - surface the AI's factor-driven decisions.

Returns what Jasper is currently watching (device watchlist + latest factor
signal per symbol) and what the factor sweep has already traded (ledger of
executed/pending/skipped tips from the Alpha Zoo Decider source).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SignalSource, SignalTip, WatchlistItem

router = APIRouter(prefix="/factor-trading", tags=["factor-trading"])


def _device_id(x_device_id: Optional[str] = Header(None)) -> str:
    return (x_device_id or "").strip() or "default-device"


def _tip_to_dict(t: SignalTip) -> Dict[str, Any]:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "side": t.side,
        "confidence": round(t.confidence or 0.0, 3),
        "rationale": t.rationale,
        "execution_status": t.execution_status,
        "executed": t.executed,
        "entry_price": t.entry_price,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


async def _factor_source_id(db: AsyncSession, device_id: str) -> Optional[int]:
    res = await db.execute(
        select(SignalSource.id).where(
            SignalSource.device_id == device_id,
            SignalSource.source_type == "factor",
        )
    )
    return res.scalar_one_or_none()


@router.get("/signals")
async def get_factor_signals(
    device_id: str = Depends(_device_id),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Latest factor-decider tips (watched + traded ledger) for the device."""
    source_id = await _factor_source_id(db, device_id)
    if source_id is None:
        return {"signals": [], "traded": [], "watching": [], "enabled": True, "counts": {"signals": 0, "traded": 0, "watching": 0}}

    tips = (
        (await db.execute(
            select(SignalTip)
            .where(SignalTip.source_id == source_id)
            .order_by(SignalTip.created_at.desc())
            .limit(limit)
        ))
        .scalars()
        .all()
    )
    traded = [_tip_to_dict(t) for t in tips if t.execution_status == "executed"]
    all_signals = [_tip_to_dict(t) for t in tips]

    # Watching = device watchlist, enriched with the latest factor signal per symbol.
    rows = (
        (await db.execute(
            select(WatchlistItem).where(WatchlistItem.device_id == device_id)
        ))
        .scalars()
        .all()
    )
    latest_by_symbol: Dict[str, Dict[str, Any]] = {}
    for t in tips:
        if t.symbol not in latest_by_symbol:
            latest_by_symbol[t.symbol] = _tip_to_dict(t)

    watching = []
    for item in rows:
        symbol = item.symbol
        signal = latest_by_symbol.get(symbol)
        watching.append({
            "symbol": symbol,
            "name": item.name,
            "asset_class": item.asset_class,
            "source": item.source,
            "last_signal": (signal.get("side") if signal else None),
            "direction": (signal.get("side") if signal else None),
            "confidence": (signal.get("confidence") if signal else None),
            "last_status": (signal.get("execution_status") if signal else None),
        })

    watching = await _enrich_prices(watching)
    return {
        "enabled": True,
        "signals": all_signals,
        "traded": traded,
        "watching": watching,
        "counts": {"signals": len(all_signals), "traded": len(traded), "watching": len(watching)},
    }


@router.get("/stats")
async def get_factor_stats(
    device_id: str = Depends(_device_id),
    db: AsyncSession = Depends(get_db),
):
    """Summary stats for the factor-decider (trades taken, watching count)."""
    source_id = await _factor_source_id(db, device_id)
    if source_id is None:
        return {"enabled": True, "trades_taken": 0, "watching": 0, "win_rate": None}

    from sqlalchemy import func

    total_res = await db.execute(
        select(func.count(SignalTip.id)).where(
            SignalTip.source_id == source_id,
            SignalTip.execution_status == "executed",
        )
    )
    total = int(total_res.scalar_one_or_none() or 0)

    watch_count = int(
        (
            await db.execute(
                select(func.count(WatchlistItem.id)).where(WatchlistItem.device_id == device_id)
            )
        ).scalar_one_or_none()
        or 0
    )

    return {
        "enabled": True,
        "trades_taken": total,
        "watching": watch_count,
        "win_rate": None,
    }


async def _enrich_prices(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Best-effort live price enrichment (never fails the listing)."""
    crypto = [i["symbol"] for i in items if i.get("asset_class") in ("crypto", None)]
    if not crypto:
        return items
    try:
        from app.services.market_data_router import get_market_data_router
        router = get_market_data_router()
        for item in items:
            if item.get("asset_class") in ("crypto", None):
                res = await router.get_price(item["symbol"])
                if res and res.get("price"):
                    item["price_usd"] = res["price"]
    except Exception:  # noqa: BLE001
        pass
    return items