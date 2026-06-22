"""
AKShare Chinese Stock Market API

Endpoints for fetching China A-shares and B-shares market data.
Uses AKShare library for real-time and historical data.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import structlog

from app.database import get_db
from app.services.akshare_service import get_akshare_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/akshare", tags=["AKShare"])


@router.get("/market-data")
async def get_market_data(
    symbol: str,
    exchange: str = Query(default="SSE", description="SSE or SZSE")
):
    """
    Get real-time market data for Chinese stock.

    Examples:
    - 600000 (SSE) - Shanghai Pudong Development Bank
    - 000001 (SZSE) - Ping An Bank
    - 688981 (SSE) - SMIC
    """
    try:
        service = get_akshare_service()
        
        if not service.is_connected:
            await service.connect()
        
        data = await service.get_market_data(symbol, exchange)
        
        if not data:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        return data
    
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical")
async def get_historical_data(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = Query(default="daily", description="daily, weekly, monthly")
):
    """
    Get historical OHLCV data for Chinese stock.

    Args:
        symbol: Stock code (e.g., 600000)
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        period: daily, weekly, or monthly
    """
    try:
        service = get_akshare_service()
        
        data = await service.get_historical_data(symbol, start_date, end_date, period)
        
        if not data:
            raise HTTPException(status_code=404, detail="No historical data found")
        
        return data
    
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
async def get_symbols(
    market: str = Query(default="A", description="A or B"),
    exchange: str = Query(default="SSE", description="SSE or SZSE")
):
    """
    Get list of available Chinese stocks.

    Args:
        market: A-shares (CNY) or B-shares (USD/HKD)
        exchange: SSE (Shanghai) or SZSE (Shenzhen)
    """
    try:
        service = get_akshare_service()
        
        # Fetch all symbols via AKShare
        if market.upper() == "A":
            df = service.akshare.stock_zh_a_spot_em()
        else:
            df = service.akshare.stock_zh_b_spot_em()
        
        symbols = []
        for _, row in df.iterrows():
            # Filter by exchange based on code prefix
            code = str(row.get('代码', ''))
            if exchange == "SSE" and code.startswith(("6", "9")):
                symbols.append({
                    "symbol": code,
                    "name": row.get('名称', ''),
                    "current": float(row.get('最新价', 0)),
                    "change_pct": float(row.get('涨跌幅', 0)),
                })
            elif exchange == "SZSE" and code.startswith(("0", "2", "3")):
                symbols.append({
                    "symbol": code,
                    "name": row.get('名称', ''),
                    "current": float(row.get('最新价', 0)),
                    "change_pct": float(row.get('涨跌幅', 0)),
                })
        
        return {"symbols": symbols[:100]}  # Limit to 100 results
    
    except Exception as e:
        logger.error(f"Failed to fetch symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get AKShare service status"""
    try:
        service = get_akshare_service()
        return service.get_status()
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/order")
async def submit_order(
    symbol: str,
    side: str,
    quantity: float,
    price: Optional[float] = None,
    order_type: str = Query(default="market")
):
    """
    Submit order for Chinese stock (paper trading only).

    Args:
        symbol: Stock code
        side: buy or sell
        quantity: Number of shares
        price: Limit price (None for market)
        order_type: market or limit
    """
    try:
        service = get_akshare_service()
        
        # Determine exchange from symbol
        exchange = "SSE" if symbol.startswith(("6", "9")) else "SZSE"
        
        result = await service.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            exchange=exchange
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return {
            "success": True,
            "order_id": result.order_id,
            "filled_price": result.filled_price,
            "message": result.message
        }
    
    except Exception as e:
        logger.error(f"Failed to submit order: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portfolio")
async def get_portfolio():
    """Get current portfolio (paper trading positions)"""
    try:
        service = get_akshare_service()
        
        positions = await service.get_positions()
        account_data = await service.get_account_data()
        
        return {
            "cash": float(account_data.cash),
            "equity": float(account_data.equity),
            "market_value": float(account_data.market_value),
            "currency": account_data.currency,
            "positions": [
                {
                    "symbol": pos.symbol,
                    "exchange": pos.exchange,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_percent": pos.unrealized_pnl_percent,
                }
                for pos in positions
            ]
        }
    
    except Exception as e:
        logger.error(f"Failed to fetch portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))