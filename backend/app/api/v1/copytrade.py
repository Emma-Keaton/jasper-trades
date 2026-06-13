"""
Copy-Trading API Endpoints

Provides:
- cTrader signal webhook ingestion
- Trader leaderboard and rankings
- Follow/unfollow traders
- Copy trading history and stats

Authentication: Device ID fingerprint via localStorage (no user accounts)
"""

from fastapi import APIRouter, HTTPException, Depends, status, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog
import uuid

from app.database import get_db
from app.models import Signal, Follow, CopyTrade, Portfolio
from app.services.ctrader_signals import CTraderSignalIngestionService
from app.services.copytrade_service import CopyTradeService

router = APIRouter(prefix="/api/v1", tags=["Copy Trading"])
logger = structlog.get_logger(__name__)


def get_device_id(x_device_id: Optional[str] = Header(None)) -> str:
    """
    Get device ID from header or generate new one.
    Frontend stores this in localStorage as fingerprint.
    """
    if x_device_id:
        return x_device_id
    return str(uuid.uuid4())


async def get_portfolio_for_device(
    device_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get or create default portfolio for device.
    Replaces user-based portfolio lookup.
    """
    result = await db.execute(
        select(Portfolio).where(Portfolio.device_id == device_id).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    
    if not portfolio:
        # Create default portfolio for this device
        portfolio = Portfolio(
            device_id=device_id,
            name="Default Portfolio",
            initial_capital=10000.0,
            is_active=True
        )
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
    
    return portfolio


# === Request/Response Models ===

class TraderLeaderboardEntry(BaseModel):
    """Trader in leaderboard"""
    trader_id: str
    trader_name: str
    total_return: float
    win_rate: float
    total_followers: int
    total_aum: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    trades_count: int
    is_verified: bool = False


class TraderProfile(BaseModel):
    """Detailed trader profile"""
    trader_id: str
    trader_name: str
    bio: Optional[str]
    trading_style: Optional[str]
    total_return: float
    win_rate: float
    total_followers: int
    total_aum: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    avg_trade_duration: Optional[float]
    total_trades: int
    winning_trades: int
    losing_trades: int
    performance_history: List[Dict[str, Any]]
    is_verified: bool = False


class FollowTraderRequest(BaseModel):
    """Follow trader request"""
    trader_id: str
    copy_percentage: float = 100.0
    max_position_size: float = 10000.0
    auto_copy: bool = True


class CopyTradeStats(BaseModel):
    """Copy trading statistics"""
    following_count: int
    total_copied_trades: int
    total_pnl: float
    avg_pnl: float
    win_rate: float
    total_signals_copied: int


# === Endpoints ===

@router.post("/ctrader/signals/webhook")
async def ctrader_signal_webhook(
    webhook_payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    cTrader webhook endpoint for receiving trade signals.
    
    cTrader calls this when a leader executes a trade.
    Automatically copies to all active followers.
    
    Returns:
        Processing result with copied count
    """
    ingestion = CTraderSignalIngestionService(db)
    result = await ingestion.process_webhook_signal(webhook_payload)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    return result


@router.get("/traders/leaderboard", response_model=List[TraderLeaderboardEntry])
async def get_trader_leaderboard(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get ranked traders by performance.
    
    Ranking criteria (configurable):
    - Total return (default)
    - Win rate
    - Sharpe ratio
    - AUM (followers' capital)
    
    Returns:
        List of traders ranked by performance
    """
    # Query follows grouped by leader
    result = await db.execute(
        select(
            Follow.leader_id,
            func.count(Follow.id).label("follower_count"),
        )
        .where(Follow.active == True)
        .group_by(Follow.leader_id)
        .order_by(func.count(Follow.id).desc())
        .limit(limit)
    )
    
    leaders = result.all()
    
    leaderboard = []
    for leader_id, follower_count in leaders:
        # Calculate performance metrics from copied trades
        trades_result = await db.execute(
            select(
                func.avg(CopyTrade.pnl).label("avg_pnl"),
                func.sum(CopyTrade.pnl).label("total_pnl"),
                func.count(CopyTrade.id).label("trade_count"),
            )
            .join(Follow, CopyTrade.follow_id == Follow.id)
            .where(Follow.leader_id == leader_id)
        )
        trade_stats = trades_result.one()
        
        # Calculate win rate
        winning_trades_result = await db.execute(
            select(func.count(CopyTrade.id))
            .join(Follow, CopyTrade.follow_id == Follow.id)
            .where(Follow.leader_id == leader_id, CopyTrade.pnl > 0)
        )
        winning_trades = winning_trades_result.scalar() or 0
        
        trade_count = trade_stats.trade_count or 1
        win_rate = (winning_trades / trade_count) * 100 if trade_count > 0 else 0
        
        leaderboard.append(
            TraderLeaderboardEntry(
                trader_id=leader_id,
                trader_name=leader_id.replace("ctrader_leader_", ""),
                total_return=float(trade_stats.total_pnl or 0),
                win_rate=round(win_rate, 2),
                total_followers=follower_count,
                total_aum=0.0,  # Would sum follower portfolio values
                max_drawdown=0.0,  # Calculate from trade history
                sharpe_ratio=None,  # Calculate from returns series
                trades_count=trade_count,
                is_verified=False,
            )
        )
    
    return leaderboard


@router.get("/traders/{trader_id}/profile", response_model=TraderProfile)
async def get_trader_profile(
    trader_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed trader profile with performance history.
    
    Returns:
        Trader profile with stats and history
    """
    # Get follower count
    follower_result = await db.execute(
        select(func.count(Follow.id))
        .where(Follow.leader_id == trader_id, Follow.active == True)
    )
    follower_count = follower_result.scalar() or 0
    
    # Get trade statistics
    trades_result = await db.execute(
        select(
            func.avg(CopyTrade.pnl).label("avg_pnl"),
            func.sum(CopyTrade.pnl).label("total_pnl"),
            func.count(CopyTrade.id).label("trade_count"),
        )
        .join(Follow, CopyTrade.follow_id == Follow.id)
        .where(Follow.leader_id == trader_id)
    )
    trade_stats = trades_result.one()
    
    # Get winning/losing trades
    winning_result = await db.execute(
        select(func.count(CopyTrade.id))
        .join(Follow, CopyTrade.follow_id == Follow.id)
        .where(Follow.leader_id == trader_id, CopyTrade.pnl > 0)
    )
    winning_trades = winning_result.scalar() or 0
    
    losing_trades = (trade_stats.trade_count or 0) - winning_trades
    
    # Calculate win rate
    trade_count = trade_stats.trade_count or 1
    win_rate = (winning_trades / trade_count) * 100 if trade_count > 0 else 0
    
    # Performance history (monthly returns)
    performance_history = []  # Would aggregate by month
    
    return TraderProfile(
        trader_id=trader_id,
        trader_name=trader_id.replace("ctrader_leader_", ""),
        bio=None,
        trading_style=None,
        total_return=float(trade_stats.total_pnl or 0),
        win_rate=round(win_rate, 2),
        total_followers=follower_count,
        total_aum=0.0,
        max_drawdown=0.0,
        sharpe_ratio=None,
        avg_trade_duration=None,
        total_trades=trade_stats.trade_count or 0,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        performance_history=performance_history,
        is_verified=False,
    )


@router.post("/traders/{trader_id}/follow")
async def follow_trader(
    trader_id: str,
    request: FollowTraderRequest,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start following a trader (auto-copy their trades).

    Args:
        trader_id: Trader to follow
        copy_percentage: How much to copy (0-100%)
        max_position_size: Maximum position size in $
        auto_copy: Automatically copy trades

    Returns:
        Follow confirmation
    """
    portfolio = await get_portfolio_for_device(device_id, db)

    copytrade_service = CopyTradeService(db)
    result = await copytrade_service.follow_trader(
        trader_id=trader_id,
        portfolio_id=portfolio.id,
        copy_percentage=request.copy_percentage,
        max_position_size=request.max_position_size,
        auto_copy=request.auto_copy,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return result


@router.post("/traders/{trader_id}/unfollow")
async def unfollow_trader(
    trader_id: str,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Stop following a trader.

    Returns:
        Unfollow confirmation
    """
    portfolio = await get_portfolio_for_device(device_id, db)

    copytrade_service = CopyTradeService(db)
    result = await copytrade_service.unfollow_trader(
        trader_id=trader_id,
        portfolio_id=portfolio.id,
    )

    return result


@router.get("/traders/following")
async def get_following_traders(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of traders current user is following.

    Returns:
        List of followed traders with copy settings
    """
    portfolio = await get_portfolio_for_device(device_id, db)
    
    if not portfolio:
        return {"following": []}

    copytrade_service = CopyTradeService(db)
    following = await copytrade_service.get_following(portfolio.id)

    return {"following": following}


@router.get("/copytrade/stats", response_model=CopyTradeStats)
async def get_copy_trading_stats(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get copy trading statistics for current user.

    Returns:
        Stats including total PnL, win rate, copied trades
    """
    portfolio = await get_portfolio_for_device(device_id, db)

    if not portfolio:
        return CopyTradeStats(
            following_count=0,
            total_copied_trades=0,
            total_pnl=0.0,
            avg_pnl=0.0,
            win_rate=0.0,
            total_signals_copied=0,
        )

    copytrade_service = CopyTradeService(db)
    stats = await copytrade_service.get_copy_trading_stats(portfolio.id)

    return CopyTradeStats(**stats)


@router.get("/copytrade/history")
async def get_copy_trade_history(
    limit: int = 50,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get history of copied trades.

    Returns:
        List of copied trades with PnL
    """
    portfolio = await get_portfolio_for_device(device_id, db)

    if not portfolio:
        return {"copy_trades": []}

    copytrade_service = CopyTradeService(db)
    copy_trades = await copytrade_service.get_copy_trades(portfolio.id, limit=limit)

    return {"copy_trades": copy_trades}