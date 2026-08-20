"""Solana Memecoin API - DexScreener discovery (search + trending) + gated trading."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.services.solana_memecoin_service import get_memecoin_service
from app.models_ext.crypto_credentials import DeviceCryptoCredential

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/memecoin", tags=["memecoin"])


class MemecoinTradeRequest(BaseModel):
    """Trade a Solana memecoin (paper via universal engine, live via Solana/Jupiter)."""
    symbol: str  # ticker or mint address
    side: str  # buy | sell
    quantity: float  # token units
    price: Optional[float] = None  # optional reference price
    wallet_address: Optional[str] = None


@router.get("/search")
async def memecoin_search(q: str = Query(..., min_length=1), limit: int = Query(10, le=25)):
    svc = get_memecoin_service()
    try:
        return {"results": await svc.search_tokens(q, limit=limit)}
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin search failed", error=str(e))
        raise HTTPException(status_code=502, detail="Memecoin search unavailable")


@router.get("/discover")
async def memecoin_discover(limit: int = Query(8, le=25)):
    """Newly launched Solana memecoins (new-token discovery)."""
    svc = get_memecoin_service()
    try:
        return {"results": await svc.discover(limit=limit)}
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin discover failed", error=str(e))
        raise HTTPException(status_code=502, detail="Discovery unavailable")


@router.get("/trending")
async def memecoin_trending(limit: int = Query(10, le=25)):
    svc = get_memecoin_service()
    try:
        return {"results": await svc.trending_v2(limit=limit)}
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin trending failed", error=str(e))
        raise HTTPException(status_code=502, detail="Trending unavailable")


@router.get("/market/{mint}")
async def memecoin_market(mint: str):
    svc = get_memecoin_service()
    try:
        data = await svc.get_market(mint)
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin market failed", error=str(e))
        raise HTTPException(status_code=502, detail="Market data unavailable")
    if not data:
        raise HTTPException(status_code=404, detail="Token not found")
    return data


async def _resolve_memecoin_price(symbol: str) -> Optional[float]:
    """Best-effort reference price: memecoin market data first, then valuation."""
    try:
        svc = get_memecoin_service()
        market = await svc.get_market(symbol)
        if market:
            return float(market.get("price_usd") or 0)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.valuation_service import ValuationService

        price = await ValuationService().get_price(symbol)
        if price and price > 0:
            return float(price)
    except Exception:  # noqa: BLE001
        pass
    return None


@router.post("/trade")
async def memecoin_trade(
    req: MemecoinTradeRequest,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Trade a Solana memecoin through the unified trade gate.

    Paper: universal paper trading engine. Live: requires a device-stored (and
    signature-verified) Solana wallet + Jupiter enabled, executing on-chain.
    """
    from app.services import trade_gate
    from app.services.paper_trading_service import get_paper_trading_service

    device_id = (x_device_id or "").strip() or "default-device"
    symbol = req.symbol
    side = req.side.lower()

    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be buy or sell")
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    price = req.price or await _resolve_memecoin_price(symbol)
    mode = await trade_gate.resolve_mode(db, device_id)

    gate = await trade_gate.check_prerequisites(
        db, device_id,
        symbol=symbol,
        side=side,
        qty=req.quantity,
        price=price or 0.0,
        intent=mode,
        asset_class="solana",
        broker="solana",
        route="memecoin",
    )
    if not gate["passed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Memecoin trade blocked: {trade_gate.describe_failures(gate)}",
        )

    if mode == "paper":
        if not price or price <= 0:
            raise HTTPException(status_code=400, detail="Could not resolve a price for paper fill")
        result = await get_paper_trading_service().place_trade(
            device_id=device_id,
            symbol=symbol,
            side=side,
            qty=req.quantity,
            price=price,
            asset_class="solana",
            agent_name="memecoin-manual",
            reasoning="Manual Solana memecoin paper order",
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return {"status": "success", "mode": "paper", "broker": "paper", **result}

    # ----- Live: build a per-device Solana client with the verified wallet -----
    from app.brokers.solana_service import SolanaBrokerService

    broker = SolanaBrokerService(config={})

    wallet_address = req.wallet_address
    if not wallet_address:
        res = await db.execute(
            select(DeviceCryptoCredential).where(
                DeviceCryptoCredential.device_id == device_id,
                DeviceCryptoCredential.exchange == "solana",
            )
        )
        cred = res.scalar_one_or_none()
        wallet_address = cred.wallet_address if cred else None
    if not wallet_address:
        raise HTTPException(status_code=400, detail="Solana wallet not configured")

    broker.wallet_address = wallet_address
    if not broker.is_connected:
        if not await broker.connect():
            raise HTTPException(status_code=502, detail="Solana RPC connection failed")

    result = await broker.submit_order(symbol=symbol, side=side, quantity=req.quantity)
    if not result.success:
        raise HTTPException(status_code=502, detail=result.message or "Solana swap failed")

    return {
        "status": "success",
        "mode": "live",
        "broker": "solana",
        "order_id": result.order_id,
        "filled_quantity": result.filled_quantity,
        "message": result.message,
    }
