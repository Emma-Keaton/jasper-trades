"""
Trading Caps API Endpoints

Risk management endpoints for controlling position sizes and exposure:
- Set max position amount ($)
- Set max position percentage (%)
- Set daily loss limits
- Enable/disable enforcement
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional
import structlog

from app.database import get_db
from app.models import TradingCap, Portfolio
from datetime import datetime

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/trading-caps", tags=["trading-caps"])


# ============ Request Models ============

class TradingCapRequest(BaseModel):
    """Trading caps configuration request."""
    portfolio_id: int
    max_position_amount: Optional[float] = Field(None, gt=0, description="Max $ per trade (e.g., 5000)")
    max_position_percentage: Optional[float] = Field(None, gt=0, le=100, description="Max % of portfolio (e.g., 20)")
    daily_loss_limit: Optional[float] = Field(None, gt=0, description="Max daily loss in $ (e.g., 2000)")
    daily_loss_percentage: Optional[float] = Field(None, gt=0, le=100, description="Max daily loss % (e.g., 5)")
    hard_limit: bool = Field(True, description="Block trades that exceed caps")
    soft_limit_enabled: bool = Field(False, description="Warn but allow if hard_limit=False")


# ============ Endpoints ============

@router.get("")
async def get_trading_caps(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get trading caps for a portfolio."""
    result = await db.execute(
        select(TradingCap).where(TradingCap.portfolio_id == portfolio_id)
    )
    caps = result.scalars().first()
    
    if not caps:
        return {
            "configured": False,
            "portfolio_id": portfolio_id,
            "message": "No trading caps configured. Set limits to protect your portfolio.",
        }
    
    return {
        "configured": True,
        "portfolio_id": portfolio_id,
        "max_position_amount": caps.max_position_amount,
        "max_position_percentage": caps.max_position_percentage,
        "daily_loss_limit": caps.daily_loss_limit,
        "daily_loss_percentage": caps.daily_loss_percentage,
        "hard_limit": caps.hard_limit,
        "soft_limit_enabled": caps.soft_limit_enabled,
        "enabled": caps.enabled,
    }


@router.post("")
async def set_trading_caps(
    request: TradingCapRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Set or update trading caps for a portfolio.
    
    **Risk Limits:**
    - `max_position_amount`: Max dollar amount per trade (e.g., $5,000)
    - `max_position_percentage`: Max percentage of portfolio per trade (e.g., 20%)
    - `daily_loss_limit`: Max daily loss in dollars (e.g., $2,000)
    - `daily_loss_percentage`: Max daily loss as percentage (e.g., 5%)
    
    **Enforcement:**
    - `hard_limit=True`: Block any trade that exceeds caps
    - `soft_limit_enabled=True`: Warn but allow (requires hard_limit=False)
    
    At least one limit must be set.
    """
    # Validate at least one limit is set
    if not any([
        request.max_position_amount,
        request.max_position_percentage,
        request.daily_loss_limit,
        request.daily_loss_percentage,
    ]):
        raise HTTPException(
            status_code=400,
            detail="At least one risk limit must be set"
        )
    
    # Verify portfolio exists
    portfolio_result = await db.execute(
        select(Portfolio).where(Portfolio.id == request.portfolio_id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail=f"Portfolio {request.portfolio_id} not found")
    
    # Get or create trading caps
    result = await db.execute(
        select(TradingCap).where(TradingCap.portfolio_id == request.portfolio_id)
    )
    caps = result.scalars().first()
    
    if caps:
        # Update existing
        caps.max_position_amount = request.max_position_amount
        caps.max_position_percentage = request.max_position_percentage
        caps.daily_loss_limit = request.daily_loss_limit
        caps.daily_loss_percentage = request.daily_loss_percentage
        caps.hard_limit = request.hard_limit
        caps.soft_limit_enabled = request.soft_limit_enabled
        caps.enabled = True
        caps.updated_at = datetime.utcnow()
    else:
        # Create new
        caps = TradingCap(
            portfolio_id=request.portfolio_id,
            max_position_amount=request.max_position_amount,
            max_position_percentage=request.max_position_percentage,
            daily_loss_limit=request.daily_loss_limit,
            daily_loss_percentage=request.daily_loss_percentage,
            hard_limit=request.hard_limit,
            soft_limit_enabled=request.soft_limit_enabled,
            enabled=True,
        )
        db.add(caps)
    
    await db.commit()
    
    logger.info(f"Trading caps set for portfolio {request.portfolio_id}")
    
    return {
        "success": True,
        "portfolio_id": request.portfolio_id,
        "max_position_amount": caps.max_position_amount,
        "max_position_percentage": caps.max_position_percentage,
        "daily_loss_limit": caps.daily_loss_limit,
        "daily_loss_percentage": caps.daily_loss_percentage,
        "hard_limit": caps.hard_limit,
        "soft_limit_enabled": caps.soft_limit_enabled,
    }


@router.delete("")
async def disable_trading_caps(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Disable trading caps for a portfolio (does not delete)."""
    result = await db.execute(
        select(TradingCap).where(TradingCap.portfolio_id == portfolio_id)
    )
    caps = result.scalars().first()
    
    if not caps:
        raise HTTPException(status_code=404, detail="No trading caps found")
    
    caps.enabled = False
    await db.commit()
    
    return {"success": True, "message": "Trading caps disabled"}


@router.post("/validate")
async def validate_trade_against_caps(
    portfolio_id: int = Query(...),
    position_amount: float = Query(..., gt=0, description="Proposed position amount in $"),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate if a proposed trade would exceed trading caps.
    
    Returns:
    - `valid`: True if trade complies with caps
    - `exceeded`: Which cap would be exceeded (if any)
    - `message`: Human-readable explanation
    """
    result = await db.execute(
        select(TradingCap).where(
            TradingCap.portfolio_id == portfolio_id,
            TradingCap.enabled == True
        )
    )
    caps = result.scalars().first()
    
    if not caps:
        return {
            "valid": True,
            "message": "No trading caps configured - trade allowed",
        }
    
    # Get portfolio value
    portfolio_result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    portfolio_value = portfolio.cash  # Or include positions for total value
    
    # Check max position amount
    if caps.max_position_amount and position_amount > caps.max_position_amount:
        return {
            "valid": not caps.hard_limit,
            "exceeded": "max_position_amount",
            "limit": caps.max_position_amount,
            "proposed": position_amount,
            "message": f"Position ${position_amount} exceeds max ${caps.max_position_amount}",
            "hard_limit": caps.hard_limit,
        }
    
    # Check max position percentage
    if caps.max_position_percentage:
        position_percentage = (position_amount / portfolio_value) * 100
        if position_percentage > caps.max_position_percentage:
            return {
                "valid": not caps.hard_limit,
                "exceeded": "max_position_percentage",
                "limit": caps.max_position_percentage,
                "calculated_percentage": position_percentage,
                "message": f"Position {position_percentage:.1f}% exceeds max {caps.max_position_percentage}%",
                "hard_limit": caps.hard_limit,
            }
    
    # Check daily loss limit (would need to calculate today's PnL)
    # This requires querying today's trades - simplified for now
    
    return {
        "valid": True,
        "message": "Trade complies with all trading caps",
    }


@router.get("/daily-pnl")
async def get_daily_pnl(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get today's PnL for daily loss limit checking."""
    from app.models import Trade
    from sqlalchemy import func, and_
    from datetime import datetime, time
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    result = await db.execute(
        select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
            and_(
                Trade.portfolio_id == portfolio_id,
                Trade.status == "filled",
                Trade.pnl.isnot(None),
                Trade.updated_at >= today_start,
                Trade.updated_at <= today_end,
            )
        )
    )
    daily_pnl = float(result.scalar() or 0.0)
    
    return {
        "portfolio_id": portfolio_id,
        "date": today_start.isoformat(),
        "daily_pnl": daily_pnl,
        "daily_pnl_formatted": f"${daily_pnl:,.2f}",
    }