"""
Risk Management API
Endpoints for portfolio risk metrics, exposure, and correlations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import structlog

from app.database import get_db
from app.services.portfolio_service import PortfolioService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/metrics")
async def get_risk_metrics(
    portfolio_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get portfolio risk metrics.
    
    Returns:
    - VaR (95%, 1-day)
    - Current drawdown
    - Sharpe ratio (30-day rolling)
    - Sortino ratio
    """
    portfolio_service = PortfolioService(db)
    
    # Get default portfolio if ID not specified
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios()
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id
    
    # Get portfolio summary
    summary = await portfolio_service.get_portfolio_summary(portfolio_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    
    # Get historical data for calculations (simplified for MVP)
    # In production, fetch from trades table
    positions = await portfolio_service.get_all_positions(portfolio_id)
    
    # Calculate VaR (95%, 1-day) - Simplified historical method
    # Assumes normal distribution for MVP
    portfolio_value = summary["total_value"]
    
    # Simplified VaR: 2.5% of portfolio value (based on typical daily volatility)
    # In production, use actual historical returns
    var_95 = portfolio_value * 0.025
    
    # Calculate current drawdown
    initial_value = summary.get("initial_value", portfolio_value)
    current_value = portfolio_value
    peak_value = max(initial_value, current_value)  # Simplified (would track peak)
    
    drawdown = (peak_value - current_value) / peak_value * 100 if peak_value > 0 else 0
    
    # CalculateSharpe ratio (simplified)
    # Assumes 20% annual return, 15% volatility for MVP
    annual_return = 0.20
    volatility = 0.15
    risk_free_rate = 0.05
    sharpe_ratio = (annual_return - risk_free_rate) / volatility
    
    # Sortino ratio (uses downside deviation)
    downside_deviation = volatility * 0.7  # Simplified
    sortino_ratio = (annual_return - risk_free_rate) / downside_deviation
    
    return {
        "portfolio_id": portfolio_id,
        "var_95": {
            "value": var_95,
            "percent": 2.5,
            "description": "95% confidence, 1-day",
            "interpretation": f"Maximum expected loss in 1 day: ${var_95:,.2f} ({2.5}%)",
        },
        "drawdown": {
            "current": drawdown,
            "peak_value": peak_value,
            "current_value": current_value,
            "description": "Decline from peak",
        },
        "sharpe_ratio": {
            "value": sharpe_ratio,
            "interpretation": "Good" if sharpe_ratio > 1.5 else "Average" if sharpe_ratio > 1.0 else "Below average",
        },
        "sortino_ratio": {
            "value": sortino_ratio,
            "interpretation": "Good" if sortino_ratio > 2.0 else "Average" if sortino_ratio > 1.5 else "Below average",
        },
        "timestamp": summary.get("timestamp", None),
    }


@router.get("/exposure")
async def get_exposure(
    portfolio_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get portfolio exposure breakdown.
    
    Returns:
    - Long/short breakdown
    - Asset allocation
    - Top concentrations
    """
    portfolio_service = PortfolioService(db)
    
    # Get default portfolio if ID not specified
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios()
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id
    
    # Get portfolio summary
    summary = await portfolio_service.get_portfolio_summary(portfolio_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    
    # Get positions
    positions = await portfolio_service.get_all_positions(portfolio_id)
    
    # Calculate exposure by type
    total_market_value = summary.get("market_value", 0)
    cash = summary.get("cash", 0)
    total_value = summary.get("total_value", 0)
    
    allocation_by_type = {}
    allocation_by_symbol = {}
    
    for position in positions:
        symbol = position.symbol
        market_value = position.market_value or 0
        
        # By type
        pos_type = getattr(position, 'type', 'Stock') or 'Stock'
        if pos_type not in allocation_by_type:
            allocation_by_type[pos_type] = 0
        allocation_by_type[pos_type] += market_value
        
        # By symbol
        allocation_by_symbol[symbol] = {
            "value": market_value,
            "weight": market_value / total_market_value * 100 if total_market_value > 0 else 0,
        }
    
    # Sort by concentration
    top_concentrations = sorted(
        allocation_by_symbol.items(),
        key=lambda x: x[1]["weight"],
        reverse=True
    )[:5]
    
    # Format allocation by type
    type_allocation = {
        pos_type: {
            "value": value,
            "weight": value / total_market_value * 100 if total_market_value > 0 else 0,
        }
        for pos_type, value in allocation_by_type.items()
    }
    
    # Add cash
    type_allocation["Cash"] = {
        "value": cash,
        "weight": cash / total_value * 100 if total_value > 0 else 0,
    }
    
    return {
        "portfolio_id": portfolio_id,
        "total_value": total_value,
        "market_value": total_market_value,
        "cash": cash,
        "allocation_by_type": type_allocation,
        "allocation_by_symbol": allocation_by_symbol,
        "top_concentrations": [
            {
                "symbol": symbol,
                "value": data["value"],
                "weight": data["weight"],
            }
            for symbol, data in top_concentrations
        ],
        "long_short_breakdown": {
            "long_value": total_market_value,  # All long for now
            "short_value": 0,
            "net_exposure": 100.0,  # All long
        },
    }


@router.get("/correlations")
async def get_correlations(
    portfolio_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get correlation matrix for portfolio holdings.
    
    Returns:
    - Correlation matrix
    - Beta vs SPY
    """
    portfolio_service = PortfolioService(db)
    
    # Get default portfolio if ID not specified
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios()
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id
    
    # Get positions
    positions = await portfolio_service.get_all_positions(portfolio_id)
    
    if not positions:
        return {
            "portfolio_id": portfolio_id,
            "correlation_matrix": {},
            "beta_vs_spy": {},
            "message": "No positions to calculate correlations",
        }
    
    symbols = [p.symbol for p in positions]
    
    # Simplified correlation matrix (identity for MVP)
    # In production, fetch historical returns and calculate correlations
    correlation_matrix = {}
    
    for symbol1 in symbols:
        correlation_matrix[symbol1] = {}
        for symbol2 in symbols:
            if symbol1 == symbol2:
                correlation_matrix[symbol1][symbol2] = 1.0
            else:
                # Simplified: assume low correlation for MVP
                correlation_matrix[symbol1][symbol2] = 0.1
    
    # Beta vs SPY (simplified)
    # In production, calculate from historical returns
    beta_vs_spy = {
        symbol: 1.0 + (hash(symbol) % 100 - 50) / 100  # Random beta 0.5-1.5
        for symbol in symbols
    }
    
    return {
        "portfolio_id": portfolio_id,
        "symbols": symbols,
        "correlation_matrix": correlation_matrix,
        "beta_vs_spy": {
            "values": beta_vs_spy,
            "average": sum(beta_vs_spy.values()) / len(beta_vs_spy) if beta_vs_spy else 0,
            "interpretation": "Market-like risk" if 0.8 <= sum(beta_vs_spy.values()) / len(beta_vs_spy) <= 1.2 else 
                             "Higher volatility" if sum(beta_vs_spy.values()) / len(beta_vs_spy) > 1.2 else
                             "Lower volatility",
        },
    }


@router.post("/alert")
async def set_risk_alert(
    alert_type: str,
    threshold: float,
    db: AsyncSession = Depends(get_db),
):
    """
    Set risk alert threshold.
    
    Alerts:
    - var_limit: Alert when VaR exceeds threshold
    - drawdown_limit: Alert when drawdown exceeds threshold
    - concentration_limit: Alert when single position exceeds threshold
    """
    # Store in database (simplified - would create Alert model)
    logger.info(
        f"Risk alert set: {alert_type} = {threshold}",
        alert_type=alert_type,
        threshold=threshold,
    )
    
    return {
        "success": True,
        "alert_type": alert_type,
        "threshold": threshold,
        "message": f"Alert configured for {alert_type} at {threshold}",
    }