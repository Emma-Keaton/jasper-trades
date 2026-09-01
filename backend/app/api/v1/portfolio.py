"""
Portfolio management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime
import structlog

from app.database import get_db
from app.services.portfolio_service import PortfolioService
from app.services.valuation_service import ValuationService
from app.models import PortfolioSnapshot
from sqlalchemy import select
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("")
async def get_portfolio(
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio summary."""
    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

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

    # Update position prices (real-time valuation)
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    positions = await portfolio_service.get_all_positions(portfolio_id)

    if positions:
        # Fetch current prices
        prices = await valuation_service.get_prices([p.symbol for p in positions])

        # Update positions with current prices
        await portfolio_service.update_position_prices(portfolio_id, prices)

        # Refresh summary
        summary = await portfolio_service.get_portfolio_summary(portfolio_id)

    return summary


@router.get("/performance")
async def get_performance(
    portfolio_id: Optional[int] = None,
    period: str = "1d",
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio performance."""
    portfolio_service = PortfolioService(db)

    # Get default portfolio
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios()
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id

    # Check if portfolio is initialized
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    positions = await portfolio_service.get_all_positions(portfolio_id)
    pnl_data = await portfolio_service.get_pnl(portfolio_id)
    is_initialized = pnl_data.get("trade_count", 0) > 0 or len(positions) > 0

    # If not initialized, return zeroed PnL
    if not is_initialized:
        return {
            "period": period,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "is_initialized": False,
        }

    # Calculate time range
    now = datetime.utcnow()

    if period == "1d":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "1w":
        start_date = now
    elif period == "1m":
        start_date = now
    elif period == "ytd":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    else:
        start_date = None
        end_date = None

    # Get PnL
    pnl = await portfolio_service.get_pnl(portfolio_id, start_date, end_date)

    return {
        "period": period,
        "realized_pnl": pnl["realized_pnl"],
        "unrealized_pnl": pnl["unrealized_pnl"],
        "total_pnl": pnl["total_pnl"],
        "trade_count": pnl["trade_count"],
        "is_initialized": True,
    }


@router.post("")
async def create_portfolio(
    name: str,
    initial_cash: float = 10000.0,
    is_paper: bool = True,
    broker: str = "ctrader",
    db: AsyncSession = Depends(get_db),
):
    """Create a new portfolio."""
    portfolio_service = PortfolioService(db)

    portfolio = await portfolio_service.create_portfolio(
        name=name,
        initial_cash=initial_cash,
        is_paper=is_paper,
        broker=broker,
    )

    return {
        "status": "success",
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "initial_cash": portfolio.cash,
    }


@router.get("/{portfolio_id}/positions")
async def get_positions(
    portfolio_id: int,
    include_empty: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get all positions in a portfolio."""
    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty)

    # Update with current prices
    if positions:
        prices = await valuation_service.get_prices([p.symbol for p in positions])
        await portfolio_service.update_position_prices(portfolio_id, prices)
        positions = await portfolio_service.get_all_positions(portfolio_id, include_empty)

    return {
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_percent": p.unrealized_pnl_percent,
            }
            for p in positions
        ]
    }


@router.get("/{portfolio_id}/holdings")
async def get_holdings(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio holdings (alias for positions endpoint)."""
    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty=False)

    # Update with current prices
    if positions:
        prices = await valuation_service.get_prices([p.symbol for p in positions])
        await portfolio_service.update_position_prices(portfolio_id, prices)
        positions = await portfolio_service.get_all_positions(portfolio_id, include_empty=False)

    return {
        "holdings": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_percent": p.unrealized_pnl_percent,
            }
            for p in positions
        ]
    }


@router.get("/{portfolio_id}/cash")
async def get_cash(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get cash balance for a portfolio."""
    portfolio_service = PortfolioService(db)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return {
        "portfolio_id": portfolio_id,
        "cash": portfolio.cash,
        "currency": "USD",
    }


@router.post("/{portfolio_id}/cash")
async def update_cash(
    portfolio_id: int,
    amount: float,
    description: str = "cash adjustment",
    db: AsyncSession = Depends(get_db),
):
    """Add or withdraw cash from portfolio."""
    portfolio_service = PortfolioService(db)

    portfolio = await portfolio_service.update_cash(portfolio_id, amount, description)

    return {
        "status": "success",
        "portfolio_id": portfolio.id,
        "old_cash": portfolio.cash - amount,
        "new_cash": portfolio.cash,
        "amount": amount,
    }


@router.get("/{portfolio_id}/allocation")
async def get_allocation(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get asset allocation for a portfolio."""
    portfolio_service = PortfolioService(db)

    summary = await portfolio_service.get_portfolio_summary(portfolio_id)

    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])

    return {
        "portfolio_id": portfolio_id,
        "total_value": summary["total_value"],
        "allocation": summary["allocation"],
    }


@router.get("/{portfolio_id}/initialization-status")
async def get_initialization_status(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Check if portfolio is initialized with real trading activity."""
    portfolio_service = PortfolioService(db)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Check for trading activity
    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty=False)
    trades_result = await portfolio_service.get_pnl(portfolio_id)
    has_trades = trades_result.get("trade_count", 0) > 0
    has_positions = len(positions) > 0

    # Portfolio is considered "initialized" only if there's actual trading activity
    # Just having a portfolio with initial cash doesn't count
    is_initialized = has_trades or has_positions

    return {
        "portfolio_id": portfolio_id,
        "is_initialized": is_initialized,
        "has_trades": has_trades,
        "has_positions": has_positions,
        "has_account_setup": portfolio.cash > 0 and (portfolio.is_paper or portfolio.broker),
        "cash": portfolio.cash,
        "initial_value": portfolio.initial_value if is_initialized else 0,
    }


@router.get("/{portfolio_id}/equity-curve")
async def get_equity_curve(
    portfolio_id: int,
    period: str = "1m",
    db: AsyncSession = Depends(get_db),
):
    """Return daily portfolio snapshots for the equity curve chart."""
    portfolio_service = PortfolioService(db)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Calculate date range
    now = datetime.utcnow()
    period_days = {"1d": 1, "1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 3650}
    days = period_days.get(period, 30)
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    result = await db.execute(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.portfolio_id == portfolio_id,
            PortfolioSnapshot.snapshot_date >= start_date,
        )
        .order_by(PortfolioSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    # Also include initial_value as the first point if no snapshots exist yet
    equity = []
    if not snapshots:
        equity.append({
            "date": portfolio.created_at.strftime("%Y-%m-%d") if portfolio.created_at else now.strftime("%Y-%m-%d"),
            "value": portfolio.initial_value or portfolio.cash,
        })
    else:
        for snap in snapshots:
            equity.append({
                "date": snap.snapshot_date,
                "value": snap.total_value,
            })

    return {
        "portfolio_id": portfolio_id,
        "period": period,
        "initial_value": portfolio.initial_value or portfolio.cash,
        "equity": equity,
    }


@router.post("/{portfolio_id}/sync-broker")
async def sync_broker_balance(
    portfolio_id: int,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync portfolio cash and positions from live broker.

    Args:
        portfolio_id: Portfolio to sync
        force_refresh: Force refresh even if recently synced

    Returns:
        Sync status and updated portfolio summary
    """
    from app.brokers import get_broker

    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Check if portfolio is live trading
    if portfolio.is_paper:
        return {
            "status": "paper_trading",
            "message": "Portfolio is paper trading, no broker sync needed",
            "cash": portfolio.cash,
            "total_value": portfolio.cash,
        }

    # Get broker for this portfolio
    broker_name = portfolio.broker or "ctrader"
    broker = get_broker(broker_name)

    if not broker or not broker.is_connected:
        # Try to connect
        if hasattr(broker, 'connect'):
            connected = await broker.connect()
            if not connected:
                raise HTTPException(
                    status_code=503,
                    detail=f"Could not connect to {broker_name} broker"
                )

    try:
        # Fetch account data from broker
        account = await broker.get_account()

        if not account:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account data from {broker_name}"
            )

        # Update portfolio cash from broker
        old_cash = portfolio.cash
        portfolio.cash = account.cash

        # Fetch positions from broker and sync
        broker_positions = await broker.get_positions()

        # Clear existing positions first for accurate sync
        existing_positions = await portfolio_service.get_all_positions(portfolio_id)
        for pos in existing_positions:
            if pos.quantity > 0:
                await portfolio_service.reduce_position(
                    portfolio_id=portfolio_id,
                    symbol=pos.symbol,
                    quantity=pos.quantity,
                    price=pos.current_price or pos.avg_price
                )

        # Add positions from broker
        for pos_data in broker_positions:
            if pos_data.quantity > 0:
                await portfolio_service.add_position(
                    portfolio_id=portfolio_id,
                    symbol=pos_data.symbol,
                    quantity=pos_data.quantity,
                    price=pos_data.avg_price,
                    current_price=pos_data.current_price,
                )

        await db.commit()
        await db.refresh(portfolio)

        # Get updated summary
        summary = await portfolio_service.get_portfolio_summary(portfolio_id)

        logger.info(
            f"Synced portfolio with {broker_name}",
            portfolio_id=portfolio_id,
            old_cash=old_cash,
            new_cash=portfolio.cash,
            total_value=summary["total_value"],
            positions_synced=len(broker_positions),
        )

        return {
            "status": "success",
            "broker": broker_name,
            "old_cash": old_cash,
            "new_cash": portfolio.cash,
            "total_value": summary["total_value"],
            "positions_synced": len(broker_positions),
        }

    except Exception as e:
        logger.error(f"Failed to sync broker balance: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")