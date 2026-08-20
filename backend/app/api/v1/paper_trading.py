"""Universal Paper Trading API - manage the paper account + place paper trades."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
import structlog

from app.services.paper_trading_service import get_paper_trading_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/paper", tags=["paper-trading"])


def _device_id(x_device_id: Optional[str] = Header(None)) -> str:
    return x_device_id or "default-device"


class PaperTradeRequest(BaseModel):
    symbol: str
    side: str  # buy | sell
    quantity: float
    price: float
    asset_class: str = "crypto"
    commission_rate: float = 0.001
    agent_name: str = "manual"
    reasoning: str = ""


@router.get("/account")
async def paper_account(device_id: str = Depends(_device_id)):
    svc = get_paper_trading_service()
    return await svc.get_account(device_id)


@router.post("/trade")
async def paper_trade(req: PaperTradeRequest, device_id: str = Depends(_device_id)):
    if req.side.lower() not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be buy or sell")
    if req.quantity <= 0 or req.price <= 0:
        raise HTTPException(status_code=400, detail="quantity and price must be positive")

    # Paper route still runs prerequisite checks (circuit breaker / caps) so a
    # halted market cannot change the paper balance.
    from app.services import trade_gate
    from app.database import async_session

    async with async_session() as db:
        gate = await trade_gate.check_prerequisites(
            db,
            device_id,
            symbol=req.symbol.upper(),
            side=req.side.lower(),
            qty=req.quantity,
            price=req.price,
            intent="paper",
            asset_class=req.asset_class,
        )
    if not gate["passed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Paper trade blocked: {trade_gate.describe_failures(gate)}",
        )

    svc = get_paper_trading_service()
    result = await svc.place_trade(
        device_id=device_id,
        symbol=req.symbol.upper(),
        side=req.side.lower(),
        qty=req.quantity,
        price=req.price,
        asset_class=req.asset_class,
        commission_rate=req.commission_rate,
        agent_name=req.agent_name,
        reasoning=req.reasoning,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/reset")
async def paper_reset(device_id: str = Depends(_device_id)):
    svc = get_paper_trading_service()
    return await svc.reset_account(device_id)
