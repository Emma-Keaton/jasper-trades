"""
Trove API Trading Router
Nigerian (NGX) and US stocks trading via Trove Finance API
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
import asyncio
import structlog
import os
import httpx
from datetime import datetime

from app.database import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()

# Trove API configuration
TROVE_BASE_URL = os.getenv("TROVE_BASE_URL", "https://sandbox.api.trovefinance.com/v1")
TROVE_API_KEY = os.getenv("TROVE_API_KEY")
TROVE_ENABLED = os.getenv("TROVE_ENABLED", "false").lower() == "true"


class TroveSymbol(BaseModel):
    """Trove stock symbol info"""
    symbol: str
    name: str
    exchange: str
    currency: str
    type: str = "stock"


class TroveOrderRequest(BaseModel):
    """Order request for Trove API"""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: int
    order_type: str = "market"  # "market" or "limit"
    price: Optional[float] = None  # For limit orders
    is_sandbox: bool = True


class TroveOrderResponse(BaseModel):
    """Order response from Trove API"""
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: int
    filled_quantity: int = 0
    price: Optional[float] = None
    created_at: datetime


class TrovePosition(BaseModel):
    """Position in Trove account"""
    symbol: str
    quantity: int
    average_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


@router.get("/trove/symbols", response_model=List[TroveSymbol], tags=["trove"])
async def get_trove_symbols():
    """
    Get list of available symbols on Trove API.
    
    Returns available Nigerian (NGX) and US stocks that can be traded.
    """
    if not TROVE_API_KEY:
        raise HTTPException(status_code=400, detail="Trove API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TROVE_BASE_URL}/market/symbols",
                headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse and return symbols
            symbols = []
            for item in data.get("symbols", []):
                symbols.append(TroveSymbol(
                    symbol=item.get("symbol", ""),
                    name=item.get("name", ""),
                    exchange=item.get("exchange", ""),
                    currency=item.get("currency", "NGN"),
                    type=item.get("type", "stock")
                ))
            
            return symbols
            
    except httpx.HTTPError as e:
        logger.error(f"Trove API error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch Trove symbols: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch symbols")


@router.get("/trove/quote/{symbol}", response_model=Dict[str, Any], tags=["trove"])
async def get_trove_quote(symbol: str):
    """
    Get real-time quote for a specific symbol.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL" for Apple, "GTCO" for Guaranty Trust Holding)
    """
    if not TROVE_API_KEY:
        raise HTTPException(status_code=400, detail="Trove API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TROVE_BASE_URL}/market/quote/{symbol}",
                headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPError as e:
        logger.error(f"Trove API quote error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch Trove quote: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch quote")


@router.post("/trove/order", response_model=TroveOrderResponse, tags=["trove"])
async def place_trove_order(
    order: TroveOrderRequest,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Place a trade order via Trove API (paper->paper engine; live->Trove API).

    Args:
        symbol: Stock symbol to trade
        side: "buy" or "sell"
        quantity: Number of shares
        order_type: "market" or "limit"
        price: Limit price (required for limit orders)
        is_sandbox: Use sandbox environment (default: True)
    """
    from app.services import trade_gate
    from app.services.paper_trading_service import get_paper_trading_service

    device_id = (x_device_id or "").strip() or "default-device"

    # Validate limit order
    if order.order_type == "limit" and order.price is None:
        raise HTTPException(status_code=400, detail="Price required for limit orders")

    # Validate side
    if order.side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")

    mode = await trade_gate.resolve_mode(db, device_id)

    # ----- Practice -> universal paper engine -----
    if mode == "paper":
        price = order.price or await _best_market_price(order.symbol)
        if not price or price <= 0:
            raise HTTPException(status_code=400, detail="Could not resolve a market price for this symbol")

        result = await get_paper_trading_service().place_trade(
            device_id=device_id,
            symbol=order.symbol.upper(),
            side=order.side,
            qty=float(order.quantity),
            price=float(price),
            asset_class="stocks",
            agent_name="trove-paper",
            reasoning=f"Trove paper order ({order.order_type})",
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        logger.info(
            "Trove paper order placed", symbol=order.symbol, side=order.side,
            quantity=order.quantity, device_id=device_id,
        )
        return TroveOrderResponse(
            order_id="paper-" + str(result.get("trade_count", 0)),
            status="filled",
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            filled_quantity=order.quantity,
            price=price,
            created_at=datetime.now(),
        )

    # ----- Live -> Trove API (gated) -----
    credentials = await _get_trove_credentials(db, device_id)
    if not credentials:
        raise HTTPException(status_code=400, detail="Trove API key not configured")

    gate = await trade_gate.check_prerequisites(
        db, device_id,
        symbol=order.symbol,
        side=order.side,
        qty=float(order.quantity),
        price=order.price or 0.0,
        intent="live",
        asset_class="stocks",
        broker="trove",
        route="trove",
    )
    if not gate["passed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Live Trove trade blocked: {trade_gate.describe_failures(gate)}",
        )

    base_url = credentials["base_url"]
    api_key = credentials["api_key"]

    target_url = f"{base_url}/trading/order"

    try:
        payload = {
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "type": order.order_type,
            "sandbox": order.is_sandbox
        }
        
        if order.price:
            payload["price"] = order.price
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                target_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(
                "Trove order placed",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_id=data.get("order_id"),
                device_id=device_id
            )
            
            return TroveOrderResponse(
                order_id=data.get("order_id", ""),
                status=data.get("status", "pending"),
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=data.get("filled_quantity", 0),
                price=data.get("price"),
                created_at=datetime.now()
            )
            
    except httpx.HTTPError as e:
        logger.error(f"Trove order error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to place Trove order: {e}")
        raise HTTPException(status_code=500, detail="Failed to place order")


async def _best_market_price(symbol: str) -> Optional[float]:
    """Fallback price lookup for paper Trove orders (valuation service)."""
    try:
        from app.services.valuation_service import ValuationService

        return await ValuationService().get_price(symbol)
    except Exception:  # noqa: BLE001
        return None


async def _get_trove_credentials(
    db: AsyncSession, device_id: str
) -> Optional[Dict[str, Any]]:
    """Trove API key/base URL from per-device DB settings (env fallback)."""
    from sqlalchemy import select
    from app.models import DeviceSettings
    from app.services.encryption import EncryptionHelper

    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    ds = res.scalar_one_or_none()
    if ds and ds.trove_api_key:
        encryption = EncryptionHelper()
        return {
            "api_key": encryption.decrypt(ds.trove_api_key),
            "base_url": ds.trove_base_url or TROVE_BASE_URL,
        }
    if TROVE_API_KEY:
        return {"api_key": TROVE_API_KEY, "base_url": TROVE_BASE_URL}
    return None


@router.get("/trove/positions", response_model=List[TrovePosition], tags=["trove"])
async def get_trove_positions(x_device_id: Optional[str] = Header(None)):
    """
    Get current positions in Trove account.
    
    Returns all open positions with unrealized P&L.
    """
    if not TROVE_API_KEY:
        raise HTTPException(status_code=400, detail="Trove API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TROVE_BASE_URL}/portfolio/positions",
                headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            positions = []
            for item in data.get("positions", []):
                positions.append(TrovePosition(
                    symbol=item.get("symbol", ""),
                    quantity=item.get("quantity", 0),
                    average_cost=item.get("average_cost", 0),
                    current_price=item.get("current_price", 0),
                    market_value=item.get("market_value", 0),
                    unrealized_pnl=item.get("unrealized_pnl", 0),
                    unrealized_pnl_percent=item.get("unrealized_pnl_percent", 0)
                ))
            
            logger.info(f"Retrieved {len(positions)} Trove positions for device {x_device_id}")
            return positions
            
    except httpx.HTTPError as e:
        logger.error(f"Trove positions error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch Trove positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


@router.get("/trove/balance", response_model=Dict[str, Any], tags=["trove"])
async def get_trove_balance(x_device_id: Optional[str] = Header(None)):
    """
    Get Trove account balance.
    
    Returns available buying power and total portfolio value.
    """
    if not TROVE_API_KEY:
        raise HTTPException(status_code=400, detail="Trove API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TROVE_BASE_URL}/portfolio/balance",
                headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Retrieved Trove balance for device {x_device_id}")
            return {
                "available_cash": data.get("available_cash", 0),
                "total_value": data.get("total_value", 0),
                "currency": data.get("currency", "NGN"),
                "updated_at": data.get("updated_at")
            }
            
    except httpx.HTTPError as e:
        logger.error(f"Trove balance error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch Trove balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@router.post("/trove/cancel/{order_id}", response_model=Dict[str, Any], tags=["trove"])
async def cancel_trove_order(order_id: str):
    """
    Cancel a pending Trove order.
    
    Args:
        order_id: The order ID to cancel
    """
    if not TROVE_API_KEY:
        raise HTTPException(status_code=400, detail="Trove API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TROVE_BASE_URL}/trading/order/{order_id}/cancel",
                headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Cancelled Trove order {order_id}")
            return {
                "success": True,
                "order_id": order_id,
                "status": data.get("status", "cancelled")
            }
            
    except httpx.HTTPError as e:
        logger.error(f"Trove cancel error: {e}")
        raise HTTPException(status_code=502, detail=f"Trove API error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to cancel Trove order: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel order")


@router.get("/trove/status", response_model=Dict[str, Any], tags=["trove"])
async def get_trove_status():
    """
    Check Trove API connection status.
    
    Returns whether Trove integration is configured and operational.
    """
    is_configured = bool(TROVE_API_KEY and TROVE_BASE_URL)
    is_enabled = TROVE_ENABLED
    
    status = {
        "configured": is_configured,
        "enabled": is_enabled,
        "sandbox": "sandbox" in TROVE_BASE_URL if TROVE_BASE_URL else False,
        "base_url": TROVE_BASE_URL
    }
    
    if is_configured:
        # Test connection
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TROVE_BASE_URL}/health",
                    headers={"Authorization": f"Bearer {TROVE_API_KEY}"},
                    timeout=5.0
                )
                status["connection"] = response.status_code == 200
        except:
            status["connection"] = False
    
    return status