"""
Watchlist API - durable, per-device list of symbols to monitor.

Kept explicitly separate from the transient /market-data/trending feed:
trending is provider-driven and volatile; the watchlist is user-owned and
survives redeploys (stored in the database).
"""
from __future__ import annotations

import asyncio
import time
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


# ---------------------------------------------------------------------------
# In-memory price cache (60 s TTL) — avoids hammering CoinGecko on every
# GET /watchlist call.
# ---------------------------------------------------------------------------
_PRICE_CACHE: Dict[str, tuple] = {}  # symbol -> (price, change, ts)
_CACHE_TTL = 60  # seconds


def _cache_get(symbol: str) -> Optional[Dict[str, Any]]:
    entry = _PRICE_CACHE.get(symbol)
    if entry and (time.monotonic() - entry[2]) < _CACHE_TTL:
        return {"price_usd": entry[0], "price_change_24h": entry[1]}
    return None


def _cache_set(symbol: str, price: Any, change: Any) -> None:
    _PRICE_CACHE[symbol] = (price, change, time.monotonic())


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
    """Best-effort live price + 24h change enrichment.

    Uses an in-memory 60 s cache and batched CoinGecko calls so that the
    watchlist endpoint responds in < 1 s even with 12 symbols.  The entire
    enrichment is wrapped in a 5 s timeout so a slow provider never blocks
    the response.
    """
    if not items:
        return items

    async def _do_enrich() -> Any:
        # --- Crypto items ---
        crypto_items = [i for i in items if i.get("asset_class") in ("crypto", None)]
        if crypto_items:
            # Step 1: Fill from cache, collect symbols that need fresh data
            need_fresh: list[str] = []
            for item in crypto_items:
                sym = item["symbol"]
                cached = _cache_get(sym)
                if cached:
                    item["price_usd"] = cached["price_usd"]
                    item["price_change_24h"] = cached["price_change_24h"]
                else:
                    need_fresh.append(sym)

            # Step 2: Batched CoinGecko price + change in ONE call
            if need_fresh:
                try:
                    import httpx
                    from app.services.market_data_router import _symbol_to_coingecko_id

                    # Map tickers → CoinGecko IDs
                    sym_to_id: Dict[str, str] = {}
                    for sym in need_fresh[:8]:
                        cid = _symbol_to_coingecko_id(sym)
                        if cid:
                            sym_to_id[sym.lower()] = cid

                    if sym_to_id:
                        coin_ids = list(sym_to_id.values())
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            resp = await client.get(
                                "https://api.coingecko.com/api/v3/simple/price",
                                params={
                                    "ids": ",".join(coin_ids),
                                    "vs_currencies": "usd",
                                    "include_24hr_change": "true",
                                },
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                for sym, cid in sym_to_id.items():
                                    coin_data = data.get(cid, {})
                                    price = coin_data.get("usd")
                                    change = coin_data.get("usd_24h_change")
                                    if price is not None:
                                        _cache_set(sym.upper(), price, round(change, 2) if change is not None else None)
                                        for item in crypto_items:
                                            if item["symbol"].lower() == sym:
                                                item["price_usd"] = price
                                                if change is not None:
                                                    item["price_change_24h"] = round(change, 2)
                            # CoinGecko rate-limited — skip silently
                except Exception:  # noqa: BLE001
                    pass

            # Step 3: For any still-missing prices, try the router chain (single provider per symbol)
            missing = [i for i in crypto_items if not i.get("price_usd")]
            if missing:
                try:
                    from app.services.market_data_router import get_market_data_router
                    router_svc = get_market_data_router()
                    results = await asyncio.gather(
                        *[router_svc.get_price(i["symbol"]) for i in missing[:4]],
                        return_exceptions=True,
                    )
                    for item, res in zip(missing, results):
                        if isinstance(res, dict) and res.get("price"):
                            item["price_usd"] = res["price"]
                            _cache_set(item["symbol"], res["price"], item.get("price_change_24h"))
                except Exception:  # noqa: BLE001
                    pass

        # --- Stock items ---
        stock_items = [i for i in items if i.get("asset_class") in ("stocks", "cn")]
        if stock_items:
            try:
                from app.services.market_data_providers import get_market_data_service
                svc = get_market_data_service()
                if svc.config.get("finnhub_key"):
                    results = await asyncio.gather(
                        *[svc.get_stock_price_finnhub(i["symbol"]) for i in stock_items[:6]],
                        return_exceptions=True,
                    )
                    for item, res in zip(stock_items, results):
                        if isinstance(res, dict) and res.get("success"):
                            d = res["data"]
                            item["price_usd"] = d.get("price")
                            item["price_change_24h"] = d.get("change_percent")
            except Exception:  # noqa: BLE001
                pass

        return items

    try:
        return await asyncio.wait_for(_do_enrich(), timeout=5.0)
    except asyncio.TimeoutError:
        # Return items without enrichment rather than blocking the response
        return items