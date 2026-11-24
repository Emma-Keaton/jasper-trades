"""Strategy Suite API — self-learning strategies proposed by the architect,
backtest-gated, promoted/retired, and evaluated on the rotating watchlist."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.device_auth import require_device_id
from app.services.strategy_suite import StrategySuiteService, run_suite_cycle

router = APIRouter(prefix="/strategy-suite", tags=["strategy-suite"])


def _device_id_dep(x_device_id: Optional[str] = Header(None, alias="X-Device-ID")) -> str:
    return require_device_id(x_device_id)


class ProposeRequest(BaseModel):
    target_confidence: float = 70.0


class StatusRequest(BaseModel):
    status: str  # draft | active | retired


@router.get("/status")
async def suite_status(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return await StrategySuiteService(db).status(device_id)


@router.get("/strategies")
async def list_strategies(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return {"strategies": await StrategySuiteService(db).list_strategies(device_id)}


@router.post("/propose")
async def propose(
    req: ProposeRequest,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return await StrategySuiteService(db).propose_strategy(device_id, req.target_confidence)


@router.post("/strategies/{strategy_id}/status")
async def set_strategy_status(
    strategy_id: int,
    req: StatusRequest,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return await StrategySuiteService(db).set_status(device_id, strategy_id, req.status)


@router.post("/run")
async def run_cycle(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    return await run_suite_cycle(db, device_id=device_id)
