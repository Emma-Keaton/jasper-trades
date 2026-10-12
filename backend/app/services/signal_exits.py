"""Periodic monitor that closes paper positions breaching their stop-loss / take-profit.

Signal tips carry LLM-extracted SL/TP levels into the paper ledger
(``place_trade(stop_loss=..., take_profit=...)`` stores them on the position).
This loop is the exit side of that bracket: every tick it asks each device's
paper service to check open bracketed positions against live prices and close
the ones that trigger, via the same sell path a manual close would use (so the
trade-monitor learning hook and auto-payout see the close like any other).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import structlog
from sqlalchemy import select

from app.database import async_session
from app.models import DeviceSettings
from app.services.paper_trading_service import get_paper_trading_service

logger = structlog.get_logger(__name__)


async def signal_exits_tick() -> Dict[str, Any]:
    """One pass over every device's paper bracket positions."""
    svc = get_paper_trading_service()
    out: List[Dict[str, Any]] = []
    async with async_session() as db:
        res = await db.execute(select(DeviceSettings.device_id))
        device_ids = [row for row in res.scalars().all()]
    for device_id in device_ids:
        try:
            closed = await svc.check_brackets(device_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("signal-exits device failed", device_id=device_id, error=str(e)[:200])
            continue
        if closed:
            out.append({"device_id": device_id, "closed": closed})
    return {"devices": out, "closes": sum(len(d["closed"]) for d in out)}


async def start_signal_exit_monitor(poll_s: int = 45) -> None:
    """Background loop: check SL/TP brackets every `poll_s` seconds."""
    while True:
        try:
            await signal_exits_tick()
        except Exception as e:  # noqa: BLE001
            logger.error("signal-exits tick failed", error=str(e)[:200])
        await asyncio.sleep(poll_s)
