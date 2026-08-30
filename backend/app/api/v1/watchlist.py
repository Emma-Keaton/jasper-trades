"""
Watchlist API - durable, per-device list of symbols to monitor.

Kept explicitly separate from the transient /market-data/trending feed:
trending is provider-driven and volatile; the watchlist is user-owned and
survives redeploys (stored in the database).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _device_id(x_device_id: Optional[str] = Header(None)) -> str:
    return (x_device_id or "").strip() or "default-device"


class WatchlistAdd(BaseModel):
    symbol: str
    name: Optional[str] = None
    asset_class: str = "crypto"
    source: Optional[str] = None


@router.get("")
async def get_watchlist(
    device_id: str = Depends(_device_id),
    db: AsyncSession = Depends(get_db),
):
    """List the device's watchlist (with live prices when available)."""
    per_device = device_id != "default-device"
    if per_device:
        rows = (await db.execute(select(WatchlistItem).where(WatchlistItem.device_id == device_id))).scalars().all()
    else:
        rows = (await db.execute(select(WatchlistItem))).scalars().all()

    items = [row_to_dict(r) for r in rows]
    items = await _enrich(items)
    return {"watchlist": items, "count": len(items)}


@router.post("")
async def add_watchlist_item(
    req: WatchlistAdd,
    device_id: str = Depends(_device_id),
    db: AsyncSession = Depends(get_db),
):
    """Pin a symbol to the watchlist (idempotent per device, max 12)."""
    symbol = req.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    # Enforce 12-item cap
    count_result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.device_id == device_id)
    )
    current_count = len(count_result.scalars().all())
    if current_count >= 12:
        raise HTTPException(
            status_code=409,
            detail="Watchlist is full. Remove an item first (max 12).",
        )

    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.device_id == device_id, WatchlistItem.symbol == symbol
        )
    )
    if existing.scalar_one_or_none():
        return {"success": True, "already_watched": True, "symbol": symbol}

    item = WatchlistItem(
        device_id=device_id,
        symbol=symbol,
        name=(req.name or "").strip()[:128] or None,
        asset_class=(req.asset_class or "crypto")[:32],
        source=(req.source or None)[:64] if req.source else None,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Kick the real-time CCXT ticker watcher for crypto symbols so a newly
    # pinned coin starts streaming without waiting for the next startup.
    if (req.asset_class or "crypto").lower() in ("crypto", "solana", "defi"):
        try:
            from app.services.ccxt_watch_service import get_ccxt_watch_service

            await get_ccxt_watch_service().watch([symbol])
        except Exception:  # noqa: BLE001
            pass

    return {"success": True, "already_watched": False, "item": row_to_dict(item)}


@router.delete("/{symbol}")
async def remove_watchlist_item(
    symbol: str,
    device_id: str = Depends(_device_id),
    db: AsyncSession = Depends(get_db),
):
    """Unpin a symbol from the watchlist."""
    sym = symbol.strip().upper()
    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.device_id == device_id, WatchlistItem.symbol == sym
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail=f"{sym} not in watchlist")
    await db.delete(item)
    await db.commit()
    return {"success": True, "symbol": sym}


def row_to_dict(row: WatchlistItem) -> Dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "name": row.name,
        "asset_class": row.asset_class,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "price_usd": None,
        "price_change_24h": None,
    }


async def _enrich(items: Any) -> Any:
    """Best-effort live price enrichment (never fails the listing)."""
    crypto_symbols = [i["symbol"] for i in items if i.get("asset_class") in ("crypto", None)]
    if not crypto_symbols:
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