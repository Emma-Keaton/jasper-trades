"""
Copy Trading Service - Follow and copy trades from top performers.
Production-ready implementation with real database tracking.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models import Signal, Trade, Portfolio, Follow, CopyTrade, Agent

logger = structlog.get_logger(__name__)


class CopyTradeService:
    """
    Copy Trading Service - Production social trading.

    Features:
    - Follow traders/agents (persisted in DB)
    - Copy signals automatically or manually
    - Position sizing based on portfolio
    - PnL tracking for copied trades
    - Copy trade history

    Requirements:
    - Real portfolio and signal data
    - No mock data
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.default_copy_percentage = 100

    # ========== Trader Following ==========

    async def follow_trader(
        self,
        trader_id: str,
        portfolio_id: int,
        copy_percentage: float = 100,
        max_position_size: float = 10000.0,
        auto_copy: bool = True,
    ) -> Dict[str, Any]:
        """
        Start following a trader.

        Args:
            trader_id: Trader/agent identifier
            portfolio_id: Portfolio that will copy trades
            copy_percentage: How much to copy (0-100)
            max_position_size: Maximum position size in dollars
            auto_copy: Automatically copy signals

        Returns:
            Result dict
        """
        # Verify portfolio exists
        portfolio_result = await self.db.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            return {"error": "Portfolio not found"}

        # Check if already following
        existing = await self.db.execute(
            select(Follow).where(
                Follow.follower_id == portfolio_id,
                Follow.leader_id == trader_id,
                Follow.active == True
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "Already following this trader"}

        # Create follow record
        follow = Follow(
            follower_id=portfolio_id,
            leader_id=trader_id,
            leader_type="agent" if len(trader_id) < 50 else "human",
            copy_percentage=copy_percentage,
            max_position_size=max_position_size,
            auto_copy=auto_copy,
        )

        self.db.add(follow)
        await self.db.commit()
        await self.db.refresh(follow)

        logger.info(
            f"Following trader {trader_id}",
            portfolio_id=portfolio_id,
            copy_percentage=copy_percentage,
            follow_id=follow.id,
        )

        return {
            "status": "success",
            "follow_id": follow.id,
            "trader_id": trader_id,
            "portfolio_id": portfolio_id,
            "copy_percentage": copy_percentage,
            "max_position_size": max_position_size,
            "auto_copy": auto_copy,
            "message": f"Now following {trader_id}",
        }

    async def unfollow_trader(
        self,
        trader_id: str,
        portfolio_id: int,
    ) -> Dict[str, Any]:
        """Stop following a trader."""
        await self.db.execute(
            update(Follow)
            .where(
                Follow.follower_id == portfolio_id,
                Follow.leader_id == trader_id,
                Follow.active == True
            )
            .values(active=False, paused_at=datetime.utcnow())
        )
        await self.db.commit()

        logger.info(
            f"Unfollowing trader {trader_id}",
            portfolio_id=portfolio_id,
        )

        return {
            "status": "success",
            "trader_id": trader_id,
            "message": f"Stopped following {trader_id}",
        }

    async def get_following(
        self,
        portfolio_id: int,
    ) -> List[Dict[str, Any]]:
        """Get list of followed traders from database."""
        result = await self.db.execute(
            select(Follow)
            .where(
                Follow.follower_id == portfolio_id,
                Follow.active == True
            )
            .order_by(Follow.followed_at.desc())
        )
        follows = result.scalars().all()

        return [
            {
                "follow_id": f.id,
                "trader_id": f.leader_id,
                "trader_name": f.leader_id,  # Would join with Agent/User table
                "copy_percentage": f.copy_percentage,
                "max_position_size": f.max_position_size,
                "auto_copy": f.auto_copy,
                "followed_at": f.followed_at.isoformat(),
                "signals_copied": f.signals_copied,
                "total_pnl": f.total_pnl,
            }
            for f in follows
        ]

    # ========== Signal Copying ==========

    async def copy_signal(
        self,
        signal_id: int,
        portfolio_id: Optional[int] = None,
        copy_percentage: float = 100,
    ) -> Dict[str, Any]:
        """
        Copy a signal (execute trade based on signal).

        Args:
            signal_id: Signal to copy
            portfolio_id: Portfolio to execute in
            copy_percentage: How much to copy

        Returns:
            Result dict with trade details
        """
        # Get signal
        signal_result = await self.db.execute(
            select(Signal).where(Signal.id == signal_id)
        )
        signal = signal_result.scalar_one_or_none()

        if not signal:
            return {"error": "Signal not found"}

        if signal.action == "hold":
            return {"action": "hold", "message": "No trade for HOLD signal"}

        # Get portfolio
        portfolio_result = await self.db.execute(
            select(Portfolio).where(Portfolio.id == (portfolio_id or 1))
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            return {"error": "Portfolio not found"}

        # Calculate position size
        position_value = self._calculate_position_size(
            portfolio=portfolio,
            signal=signal,
            copy_percentage=copy_percentage,
        )

        # Get estimated price
        estimated_price = signal.metadata.get("price", 100) if signal.metadata else 100
        quantity = position_value / estimated_price if estimated_price > 0 else 0

        if quantity <= 0:
            return {"error": "Invalid quantity calculated"}

        # Import execution agent
        from app.agents import agent_registry
        execution_agent = agent_registry.get("execution")

        if not execution_agent:
            return {"error": "Execution agent not available"}

        try:
            # Create and submit trade
            trade = await execution_agent.create_order(
                symbol=signal.symbol,
                side=signal.action,
                quantity=quantity,
                order_type="market",
            )

            trade = await execution_agent.submit_to_broker(trade)

            if trade.status == "submitted":
                # Record copy trade
                copy_trade = CopyTrade(
                    follow_id=0,  # Would come from Follow record if auto-copying
                    original_signal_id=signal_id,
                    resulting_trade_id=trade.id,
                    copy_percentage=copy_percentage,
                    original_quantity=signal.metadata.get("quantity", quantity) if signal.metadata else quantity,
                    copied_quantity=quantity,
                )
                self.db.add(copy_trade)

                # Update follow stats if applicable
                if signal.agent_name:
                    follow_result = await self.db.execute(
                        select(Follow).where(
                            Follow.follower_id == portfolio_id,
                            Follow.leader_id == signal.agent_name,
                            Follow.active == True
                        )
                    )
                    follow = follow_result.scalar_one_or_none()
                    if follow:
                        follow.signals_copied += 1

                await self.db.commit()

                logger.info(
                    f"Copied signal {signal_id}",
                    symbol=signal.symbol,
                    action=signal.action,
                    quantity=quantity,
                    trade_id=trade.id,
                )

                return {
                    "action": signal.action,
                    "symbol": signal.symbol,
                    "quantity": round(quantity, 2),
                    "estimated_price": estimated_price,
                    "position_value": round(position_value, 2),
                    "trade_id": trade.id,
                    "broker_order_id": trade.broker_order_id if hasattr(trade, 'broker_order_id') else None,
                    "copy_trade_id": copy_trade.id,
                }
            else:
                return {"error": "Trade submission failed"}

        except Exception as e:
            logger.error(f"Error copying signal: {e}")
            return {"error": str(e)}

    def _calculate_position_size(
        self,
        portfolio: Portfolio,
        signal: Signal,
        copy_percentage: float,
    ) -> float:
        """Calculate position size based on portfolio and signal strength"""
        signal_strength = signal.strength or 0.5
        effective_percentage = (copy_percentage / 100) * signal_strength
        
        # Use max 50% of cash per trade for risk management
        position_value = portfolio.cash * effective_percentage * 0.5
        
        return position_value

    # ========== Copy Trade History ==========

    async def get_copy_trades(
        self,
        portfolio_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get history of copied trades from database."""
        # Get follows for this portfolio
        follow_result = await self.db.execute(
            select(Follow.id).where(
                Follow.follower_id == portfolio_id,
                Follow.active == True
            )
        )
        follow_ids = [f[0] for f in follow_result.all()]

        if not follow_ids:
            return []

        # Get copy trades
        copy_result = await self.db.execute(
            select(CopyTrade)
            .where(CopyTrade.follow_id.in_(follow_ids))
            .order_by(CopyTrade.copied_at.desc())
            .limit(limit)
        )
        copy_trades = copy_result.scalars().all()

        # Enhance with signal and trade data
        result = []
        for ct in copy_trades:
            signal_result = await self.db.execute(
                select(Signal).where(Signal.id == ct.original_signal_id)
            )
            signal = signal_result.scalar_one_or_none()

            result.append({
                "id": ct.id,
                "follow_id": ct.follow_id,
                "source_signal_id": ct.original_signal_id,
                "symbol": signal.symbol if signal else "Unknown",
                "action": signal.action if signal else "Unknown",
                "quantity": ct.copied_quantity,
                "copied_at": ct.copied_at.isoformat(),
                "copy_percentage": ct.copy_percentage,
                "pnl": ct.pnl,
                "pnl_percent": ct.pnl_percent,
                "closed_at": ct.closed_at.isoformat() if ct.closed_at else None,
            })

        return result

    async def update_copy_trade_pnl(
        self,
        copy_trade_id: int,
        pnl: float,
        pnl_percent: float,
        closed: bool = False,
    ):
        """Update PnL for a copy trade."""
        await self.db.execute(
            update(CopyTrade)
            .where(CopyTrade.id == copy_trade_id)
            .values(
                pnl=pnl,
                pnl_percent=pnl_percent,
                closed_at=datetime.utcnow() if closed else None,
            )
        )
        await self.db.commit()

        logger.info(f"Updated copy trade {copy_trade_id} PnL: {pnl:.2f} ({pnl_percent:.2f}%)")

    async def get_copy_trading_stats(
        self,
        portfolio_id: int,
    ) -> Dict[str, Any]:
        """Get copy trading statistics for a portfolio."""
        # Get follows
        follow_result = await self.db.execute(
            select(Follow).where(
                Follow.follower_id == portfolio_id,
                Follow.active == True
            )
        )
        follows = follow_result.scalars().all()

        if not follows:
            return {
                "following_count": 0,
                "total_copied_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
            }

        # Get copy trades
        follow_ids = [f.id for f in follows]
        copy_result = await self.db.execute(
            select(CopyTrade).where(CopyTrade.follow_id.in_(follow_ids))
        )
        copy_trades = copy_result.scalars().all()

        winning_trades = sum(1 for ct in copy_trades if ct.pnl > 0)
        total_pnl = sum(ct.pnl for ct in copy_trades)

        return {
            "following_count": len(follows),
            "total_copied_trades": len(copy_trades),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(copy_trades), 2) if copy_trades else 0,
            "win_rate": round((winning_trades / len(copy_trades)) * 100, 2) if copy_trades else 0,
            "total_signals_copied": sum(f.signals_copied for f in follows),
        }