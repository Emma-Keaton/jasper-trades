"""
Signal management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from app.database import get_db, async_session
from app.services.signal_service import SignalService
from app.services.copytrade_service import CopyTradeService
from app.models import Agent

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("")
async def list_signals(
    symbol: Optional[str] = None,
    agent: Optional[str] = None,
    action: Optional[str] = None,
    min_strength: float = Query(default=0, ge=0, le=1),
    include_expired: bool = False,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List trading signals with filters."""
    signal_service = SignalService(db)

    signals = await signal_service.get_signals(
        symbol=symbol,
        agent_name=agent,
        action=action,
        min_strength=min_strength,
        is_public=True,
        include_expired=include_expired,
        limit=limit,
    )

    return {
        "signals": [
            {
                "id": s.id,
                "symbol": s.symbol,
                "action": s.action,
                "strength": s.strength,
                "agent_name": s.agent_name,
                "reasoning": s.reasoning,
                "created_at": s.created_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "metadata": s.metadata,
                "is_public": s.is_public,
                "copied_by": s.copied_by,
            }
            for s in signals
        ],
        "count": len(signals),
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get signal details."""
    signal_service = SignalService(db)

    signal = await signal_service.get_signal(signal_id)

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {
        "id": signal.id,
        "symbol": signal.symbol,
        "action": signal.action,
        "strength": signal.strength,
        "agent_name": signal.agent_name,
        "reasoning": signal.reasoning,
        "created_at": signal.created_at.isoformat(),
        "expires_at": signal.expires_at.isoformat(),
        "metadata": signal.metadata,
        "is_public": signal.is_public,
        "copied_by": signal.copied_by,
    }


@router.post("/{signal_id}/copy")
async def copy_signal(
    signal_id: int,
    portfolio_id: Optional[int] = None,
    copy_percentage: float = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Copy a signal (execute similar trade in own portfolio).

    Args:
        signal_id: Signal to copy
        portfolio_id: Portfolio to execute in
        copy_percentage: How much to copy (0-100)
    """
    signal_service = SignalService(db)
    copytrade_service = CopyTradeService(db)

    signal = await signal_service.get_signal(signal_id)

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if signal.action == "hold":
        return {
            "status": "skipped",
            "message": "Signal is HOLD action, no trade executed",
        }

    # Copy the signal
    result = await copytrade_service.copy_signal(
        signal_id=signal_id,
        portfolio_id=portfolio_id,
        copy_percentage=copy_percentage,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    # Update signal copied count
    await signal_service.update_signal_performance(
        signal_id=signal_id,
        outcome="copied",
    )

    return {
        "status": "success",
        "signal_id": signal_id,
        "action": result.get("action"),
        "symbol": result.get("symbol"),
        "quantity": result.get("quantity"),
        "message": f"Copied signal: {signal.action} {result.get('quantity')} {signal.symbol}",
    }


@router.post("/publish/{signal_id}")
async def publish_signal(
    signal_id: int,
    is_public: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Set signal visibility (public/private)."""
    signal_service = SignalService(db)

    signal = await signal_service.publish_signal(signal_id, is_public)

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {
        "status": "success",
        "signal_id": signal_id,
        "is_public": is_public,
    }


@router.get("/agent/{agent_name}/stats")
async def get_agent_stats(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for an agent's signal performance."""
    signal_service = SignalService(db)

    stats = await signal_service.get_agent_stats(agent_name)

    return stats


@router.get("/sync")
async def sync_signals(
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync signals from followed traders.

    For copy trading - fetches signals from GitHub Gists.
    """
    copytrade_service = CopyTradeService(db)

    # Get signals from followed traders
    signals = await copytrade_service.sync_signals(portfolio_id)

    return {
        "synced_signals": len(signals),
        "signals": signals[:20],  # Limit response
    }


@router.get("/following")
async def get_following(
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List followed traders."""
    copytrade_service = CopyTradeService(db)

    # Get followed traders
    following = await copytrade_service.get_following(portfolio_id or 1)

    return {
        "following": following,
    }


@router.post("/following/{trader_id}")
async def follow_trader(
    trader_id: str,
    portfolio_id: Optional[int] = None,
    copy_percentage: float = 100,
    db: AsyncSession = Depends(get_db),
):
    """Start following a trader."""
    copytrade_service = CopyTradeService(db)

    result = await copytrade_service.follow_trader(
        trader_id=trader_id,
        portfolio_id=portfolio_id or 1,
        copy_percentage=copy_percentage,
    )

    return result


@router.delete("/following/{trader_id}")
async def unfollow_trader(
    trader_id: str,
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Stop following a trader."""
    copytrade_service = CopyTradeService(db)

    result = await copytrade_service.unfollow_trader(
        trader_id=trader_id,
        portfolio_id=portfolio_id or 1,
    )

    return result


# ============== AI-Trader Enhanced Signal Endpoints ==============

@router.get("/enhanced/feed")
async def get_enhanced_signal_feed(
    limit: int = Query(default=20, le=100),
    message_type: Optional[str] = Query(None, description="Filter: 'position', 'strategy', 'discussion'"),
    symbol: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort: str = Query(default="new", description="Sort: 'new', 'active', 'following'"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get enhanced signal feed from AI-Trader.
    
    Three signal types:
    - position: Real-time trading positions
    - strategy: Strategy analysis and discussions  
    - discussion: Opinion posts
    """
    signal_service = SignalService(db)
    
    signals = await signal_service.get_signal_feed_enhanced(
        limit=limit,
        message_type=message_type,
        symbol=symbol,
        keyword=keyword,
        sort=sort
    )
    
    return {
        "signals": signals,
        "count": len(signals),
    }


@router.get("/enhanced/grouped")
async def get_signals_grouped_by_agent(
    limit: int = Query(default=20, le=100),
    message_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get signals grouped by agent for two-level UI.
    
    Level 1: Agent list with signal counts
    Level 2: View specific agent's signals
    """
    signal_service = SignalService(db)
    
    grouped = await signal_service.get_signals_grouped_by_agent(
        limit=limit,
        message_type=message_type
    )
    
    return {
        "agents": grouped,
        "total": len(grouped),
    }


@router.post("/enhanced/realtime")
async def publish_realtime_signal(
    market: str,
    action: str,
    symbol: str,
    price: float,
    quantity: float,
    content: Optional[str] = None,
    executed_at: Optional[str] = None,
    agent_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish real-time trading signal (position).
    
    Two methods:
    1. Sync external trade: Fill in actual trade time and price
    2. Platform simulated trade: Set executed_at="now", price=0 (auto-query)
    """
    # Get or create agent
    if not agent_name:
        # Get first active agent
        async with async_session() as session:
            result = await session.execute(
                select(Agent).filter(Agent.is_active == True).limit(1)
            )
            agent = result.scalar_one_or_none()
            if agent:
                agent_name = agent.name
                agent_id = agent.id
            else:
                agent_name = "Unknown"
                agent_id = 1
    else:
        async with async_session() as session:
            result = await session.execute(
                select(Agent).filter(Agent.name == agent_name).limit(1)
            )
            agent = result.scalar_one_or_none()
            agent_id = agent.id if agent else 1
    
    signal_service = SignalService(db)
    
    signal = await signal_service.publish_realtime_signal(
        agent_id=agent_id,
        agent_name=agent_name,
        market=market,
        action=action,
        symbol=symbol,
        price=price,
        quantity=quantity,
        content=content,
        executed_at=executed_at
    )
    
    return {
        "status": "success",
        "signal_id": signal.id,
        "signal": signal_service._signal_enhanced_to_dict(signal),
    }


@router.post("/enhanced/strategy")
async def publish_strategy(
    market: str,
    title: str,
    content: str,
    symbols: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    agent_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Publish strategy analysis."""
    # Get agent
    if not agent_name:
        async with async_session() as session:
            result = await session.execute(select(Agent).limit(1))
            agent = result.scalar_one_or_none()
            agent_name = agent.name if agent else "Unknown"
            agent_id = agent.id if agent else 1
    else:
        async with async_session() as session:
            result = await session.execute(select(Agent).filter(Agent.name == agent_name).limit(1))
            agent = result.scalar_one_or_none()
            agent_id = agent.id if agent else 1
    
    signal_service = SignalService(db)
    
    signal = await signal_service.publish_strategy(
        agent_id=agent_id,
        agent_name=agent_name,
        market=market,
        title=title,
        content=content,
        symbols=symbols,
        tags=tags
    )
    
    return {
        "status": "success",
        "signal_id": signal.id,
        "signal": signal_service._signal_enhanced_to_dict(signal),
    }


@router.post("/enhanced/discussion")
async def publish_discussion(
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    agent_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Publish discussion post."""
    # Get agent
    if not agent_name:
        async with async_session() as session:
            result = await session.execute(select(Agent).limit(1))
            agent = result.scalar_one_or_none()
            agent_name = agent.name if agent else "Unknown"
            agent_id = agent.id if agent else 1
    else:
        async with async_session() as session:
            result = await session.execute(select(Agent).filter(Agent.name == agent_name).limit(1))
            agent = result.scalar_one_or_none()
            agent_id = agent.id if agent else 1
    
    signal_service = SignalService(db)
    
    signal = await signal_service.publish_discussion(
        agent_id=agent_id,
        agent_name=agent_name,
        title=title,
        content=content,
        tags=tags
    )
    
    return {
        "status": "success",
        "signal_id": signal.id,
        "signal": signal_service._signal_enhanced_to_dict(signal),
    }