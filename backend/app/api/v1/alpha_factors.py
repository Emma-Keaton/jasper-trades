"""
Alpha Factor Zoo endpoints - Browse and manage 452 alpha factors.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.database import get_db
from app.services.alpha_factor_service import AlphaFactorService

router = APIRouter()


@router.get("")
async def list_alpha_factors(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    min_sharpe: Optional[float] = Query(default=None, ge=0),
    min_win_rate: Optional[float] = Query(default=None, ge=0, le=100),
    search: Optional[str] = Query(default=None, min_length=2),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    List alpha factors with optional filters.
    
    Returns the 452 alpha factors from the zoo.
    """
    factor_service = AlphaFactorService(db)
    
    factors = await factor_service.get_factors(
        category=category,
        difficulty=difficulty,
        min_sharpe=min_sharpe,
        min_win_rate=min_win_rate,
        search_query=search,
        limit=limit,
    )
    
    return {
        "factors": factors,
        "count": len(factors),
        "total_available": 452,
    }


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get unique factor categories."""
    factor_service = AlphaFactorService(db)
    categories = await factor_service.get_categories()
    
    return {
        "categories": categories,
    }


@router.get("/{factor_id}")
async def get_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific alpha factor."""
    factor_service = AlphaFactorService(db)
    factor = await factor_service.get_factor_by_id(factor_id)
    
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    
    return factor


@router.get("/{factor_id}/performance")
async def get_factor_performance(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get historical performance metrics for an alpha factor."""
    factor_service = AlphaFactorService(db)
    performance = await factor_service.get_factor_performance(factor_id)
    
    if not performance:
        raise HTTPException(status_code=404, detail="Factor not found")
    
    return performance


@router.post("/{factor_id}/add-to-strategy")
async def add_factor_to_strategy(
    factor_id: str,
    strategy_name: str = Query(default="Default Strategy"),
    weight: float = Query(default=1.0, ge=0.1, le=10.0),
    db: AsyncSession = Depends(get_db),
):
    """Add an alpha factor to a backtest strategy."""
    factor_service = AlphaFactorService(db)
    result = await factor_service.add_factor_to_strategy(
        factor_id=factor_id,
        strategy_name=strategy_name,
        weight=weight,
    )
    
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/ensemble/performance")
async def get_ensemble_performance(
    factor_ids: List[str],
    strategy_name: str = "Custom Ensemble",
    db: AsyncSession = Depends(get_db),
):
    """Get estimated performance metrics for a factor ensemble."""
    factor_service = AlphaFactorService(db)
    result = await factor_service.get_ensemble_performance(
        factor_ids=factor_ids,
        strategy_name=strategy_name,
    )
    
    return result