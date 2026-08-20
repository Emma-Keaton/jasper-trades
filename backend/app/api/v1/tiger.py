"""
Tiger OpenAPI Router - LIVE CN/US stock trading via each device's funded Tiger account.

Paper trading is intentionally NOT handled here: paper orders are routed to the
Universal Paper Trading engine so the paper track record stays unified. This
router only executes LIVE orders through Tiger (per-device credentials).
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
import structlog
from datetime import datetime

from app.database import get_db
from app.services.encryption import EncryptionHelper
from app.models import DeviceSettings
from app.brokers.tiger_service import (
    TigerBrokerService,
    load_tiger_client,
    normalize_tiger_symbol,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


class TigerSettingsRequest(BaseModel):
    """Tiger OpenAPI configuration (live trading only)."""
    tiger_id: str
    tiger_api_key: str
    tiger_private_key: str
    tiger_enabled: bool = True


class TigerOrderRequest(BaseModel):
    """Live order request via Tiger OpenAPI."""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str = "market"  # "market" or "limit"
    price: Optional[float] = None  # Required for limit orders
    asset_class: str = "us-stocks"  # "cn" | "us-stocks"


class TigerOrderResponse(BaseModel):
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: float
    filled_quantity: float = 0
    price: Optional[float] = None
    created_at: datetime


def _mask(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.post("/settings/tiger")
async def save_tiger_settings(
    req: TigerSettingsRequest,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Save per-device Tiger OpenAPI credentials (encrypted at rest)."""
    device_id = (x_device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    encryption = EncryptionHelper()
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if row:
        row.tiger_id = req.tiger_id
        row.tiger_api_key = encryption.encrypt(req.tiger_api_key)
        row.tiger_private_key = encryption.encrypt(req.tiger_private_key)
        row.tiger_enabled = req.tiger_enabled
    else:
        row = DeviceSettings(
            device_id=device_id,
            tiger_id=req.tiger_id,
            tiger_api_key=encryption.encrypt(req.tiger_api_key),
            tiger_private_key=encryption.encrypt(req.tiger_private_key),
            tiger_enabled=req.tiger_enabled,
        )
        db.add(row)
    await db.commit()

    logger.info("Tiger settings saved", device_id=device_id, tiger_id=req.tiger_id)
    return {
        "success": True,
        "message": "Tiger OpenAPI settings saved (live trading only)",
        "tiger_id": req.tiger_id,
        "tiger_enabled": req.tiger_enabled,
    }


@router.get("/settings/tiger")
async def get_tiger_settings(
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Read Tiger config back (API keys masked) + connection status."""
    device_id = (x_device_id or "").strip()
    if not device_id:
        return {"tiger_id": None, "tiger_api_key": None, "tiger_private_key": None,
                "tiger_enabled": False, "is_configured": False}

    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if not row or not (row.tiger_id and row.tiger_api_key and row.tiger_private_key):
        return {"tiger_id": row.tiger_id if row else None, "tiger_api_key": None,
                "tiger_private_key": None, "tiger_enabled": bool(row and row.tiger_enabled),
                "is_configured": False}

    encryption = EncryptionHelper()
    api_key = encryption.decrypt(row.tiger_api_key) or ""
    private_key = encryption.decrypt(row.tiger_private_key) or ""
    return {
        "tiger_id": row.tiger_id,
        "tiger_api_key": _mask(api_key),
        "tiger_private_key": _mask(private_key),
        "tiger_enabled": row.tiger_enabled or False,
        "is_configured": True,
    }


@router.post("/settings/tiger/test")
async def test_tiger_connection(
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Validate the device's Tiger credentials against the Tiger API."""
    device_id = (x_device_id or "").strip()
    if not device_id:
        return {"valid": False, "message": "X-Device-ID header required"}

    client = await load_tiger_client(db, device_id)
    if client is None:
        return {"valid": False, "message": "Tiger OpenAPI credentials not configured for this device"}

    ok = await client.connect()
    if not ok:
        return {"valid": False, "message": "Tiger API connection failed - check credentials"}
    account = await client.get_account()
    return {
        "valid": True,
        "message": "Tiger API connected",
        "account_id": account.account_id,
        "equity": account.equity,
        "cash": account.cash,
    }


# ---------------------------------------------------------------------------
# Live order
# ---------------------------------------------------------------------------

@router.post("/tiger/order", response_model=TigerOrderResponse, tags=["tiger"])
async def place_tiger_order(
    order: TigerOrderRequest,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Place a trade via Tiger OpenAPI (LIVE only).

    Paper intent (device in practice mode) is routed to the Universal Paper
    Trading engine. Live intent requires the device's own funded Tiger account.
    """
    from app.services import trade_gate
    from app.services.paper_trading_service import get_paper_trading_service

    device_id = (x_device_id or "").strip() or "default-device"

    if order.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if order.order_type == "limit" and order.price is None:
        raise HTTPException(status_code=400, detail="Price required for limit orders")
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    mode = await trade_gate.resolve_mode(db, device_id)
    asset_class = "cn" if order.asset_class == "cn" else "us-stocks"

    # ----- Paper intent: universal paper engine -----
    if mode == "paper":
        price = order.price
        if not price or price <= 0:
            from app.services.valuation_service import ValuationService

            price = await ValuationService().get_price(order.symbol)
        if not price or price <= 0:
            raise HTTPException(status_code=400, detail="Could not resolve a market price for paper fill")

        result = await get_paper_trading_service().place_trade(
            device_id=device_id,
            symbol=order.symbol.upper(),
            side=order.side,
            qty=float(order.quantity),
            price=float(price),
            asset_class=asset_class,
            agent_name="tiger-paper",
            reasoning=f"Tiger paper order ({order.order_type})",
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return TigerOrderResponse(
            order_id="paper-" + str(result.get("trade_count", 0)),
            status="filled",
            symbol=normalize_tiger_symbol(order.symbol),
            side=order.side,
            quantity=order.quantity,
            filled_quantity=order.quantity,
            price=price,
            created_at=datetime.now(),
        )

    # ----- Live intent: Tiger only (gated) -----
    gate = await trade_gate.check_prerequisites(
        db, device_id,
        symbol=order.symbol,
        side=order.side,
        qty=float(order.quantity),
        price=order.price or 0.0,
        intent="live",
        asset_class=asset_class,
        broker="tiger",
        route="tiger",
    )
    if not gate["passed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Live Tiger trade blocked: {trade_gate.describe_failures(gate)}",
        )

    from app.brokers.tiger_service import place_tiger_live_order

    try:
        result = await place_tiger_live_order(
            db, device_id, symbol=order.symbol, side=order.side,
            quantity=float(order.quantity), order_type=order.order_type,
            limit_price=order.price, asset_class=asset_class,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Tiger live order failed", error=str(e), device_id=device_id)
        raise HTTPException(status_code=502, detail=str(e))

    return TigerOrderResponse(
        order_id=result.get("order_id", ""),
        status="submitted",
        symbol=result.get("symbol", normalize_tiger_symbol(order.symbol)),
        side=order.side,
        quantity=order.quantity,
        filled_quantity=result.get("filled_quantity", 0),
        price=result.get("filled_price") or order.price,
        created_at=datetime.now(),
    )
