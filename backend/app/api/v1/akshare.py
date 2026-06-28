"""
AKShare Chinese Stock Market API

Endpoints for fetching China A-shares and B-shares market data.
Uses AKShare library for real-time and historical data.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import structlog
import asyncio

from app.database import get_db
from app.brokers.akshare_service import AKShareBrokerService

logger = structlog.get_logger(__name__)

# Simple in-memory cache for symbols (avoids slow AKShare API calls)
_symbols_cache: Dict[str, dict] = {}

class SimpleCache:
    """Simple in-memory cache with expiration"""
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        if key in _symbols_cache:
            cached = _symbols_cache[key]
            if datetime.utcnow() < cached['expires']:
                return cached['data']
            del _symbols_cache[key]
        return None
    
    @staticmethod
    async def set(key: str, data: Any, expire: int = 300):
        _symbols_cache[key] = {
            'data': data,
            'expires': datetime.utcnow() + timedelta(seconds=expire)
        }

cache = SimpleCache()

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
        service = AKShareBrokerService()
        
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
        service = AKShareBrokerService()
        
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
    exchange: str = Query(default="SSE", description="SSE or SZSE"),
    limit: int = Query(default=100, ge=1, le=500, description="Max symbols to return")
):
    """
    Get list of available Chinese stocks.

    Args:
        market: A-shares (CNY) or B-shares (USD/HKD)
        exchange: SSE (Shanghai) or SZSE (Shenzhen)
        limit: Maximum number of symbols to return (default: 100, max: 500)
    """
    try:
        service = AKShareBrokerService()
        
        # Use caching to avoid repeated API calls
        import asyncio
        cache_key = f"akshare_symbols_{market}_{exchange}"
        
        # Try to get from cache first
        try:
            cache_data = await cache.get(cache_key)
            if cache_data:
                # Apply limit to cached data
                return {"symbols": cache_data[:limit], "total": len(cache_data), "cached": True}
        except:
            pass

        # Fetch all symbols via AKShare with timeout
        async with asyncio.timeout(30):  # 30 second timeout
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
            
            # Stop if we've reached the limit
            if len(symbols) >= limit * 2:  # Fetch slightly more to account for filtering
                break

        # Cache for 5 minutes
        try:
            await cache.set(cache_key, symbols, expire=300)
        except:
            pass

        return {"symbols": symbols[:limit], "total": len(symbols), "cached": False}

    except asyncio.TimeoutError:
        logger.error("AKShare symbols fetch timed out after 30s")
        raise HTTPException(status_code=504, detail="Request timeout - try again later")
    except Exception as e:
        logger.error(f"Failed to fetch symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get AKShare service status"""
    try:
        service = AKShareBrokerService()
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
        service = AKShareBrokerService()
        
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
        service = AKShareBrokerService()
        
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