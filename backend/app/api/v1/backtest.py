"""
Backtest endpoints - Run and analyze historical strategy simulations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.database import get_db
from app.services.backtest_service import BacktestService

router = APIRouter()


@router.post("/run")
async def run_backtest(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Run a backtest simulation.
    
    Args:
        strategy_name: Name for the strategy
        factor_ids: List of alpha factor IDs to use
        start_date: Backtest start date (ISO format)
        end_date: Backtest end date (ISO format)
        initial_capital: Starting capital (default: $10,000)
        engine: Backtest engine (vibetrader, singlefactor, etc.)
        feed: Data feed resolution (dailyohlc, hourlyohlc, etc.)
        assets: List of assets to trade
    """
    backtest_service = BacktestService(db)
    
    try:
        # Parse dates
        start_date = datetime.fromisoformat(request.get("start_date", "2024-01-01"))
        end_date = datetime.fromisoformat(request.get("end_date", "2025-01-01"))
        
        # Validate dates
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        result = await backtest_service.run_backtest(
            strategy_name=request.get("strategy_name", "Custom Strategy"),
            factor_ids=request.get("factor_ids", []),
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.get("initial_capital", 10000.0),
            engine=request.get("engine", "vibetrader"),
            feed=request.get("feed", "dailyohlc"),
            assets=request.get("assets"),
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/{backtest_id}")
async def get_backtest_results(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get backtest results by ID."""
    backtest_service = BacktestService(db)
    results = await backtest_service.get_backtest_results(backtest_id)
    
    if not results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return results


@router.get("")
async def list_backtests(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List recent backtests."""
    backtest_service = BacktestService(db)
    backtests = await backtest_service.list_backtests(limit=limit, offset=offset)
    
    return {
        "backtests": backtests,
        "count": len(backtests),
    }


@router.post("/compare")
async def compare_strategies(
    backtest_ids: List[str] = Body(..., description="List of backtest IDs to compare"),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple backtest results side-by-side."""
    backtest_service = BacktestService(db)
    
    if len(backtest_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 backtests to compare")
    
    comparison = await backtest_service.compare_strategies(backtest_ids)
    return comparison


@router.post("/save")
async def save_backtest(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Save backtest results to database."""
    backtest_service = BacktestService(db)
    
    try:
        result = await backtest_service.save_backtest(
            name=request.get("name"),
            strategy=request.get("strategy"),
            symbol=request.get("symbol"),
            start_date=datetime.fromisoformat(request.get("start_date")),
            end_date=datetime.fromisoformat(request.get("end_date")),
            initial_capital=request.get("initial_capital"),
            final_capital=request.get("final_capital"),
            total_return=request.get("total_return"),
            sharpe_ratio=request.get("sharpe_ratio"),
            max_drawdown=request.get("max_drawdown"),
            win_rate=request.get("win_rate"),
            config=request.get("config", {}),
            trades=request.get("trades", []),
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")