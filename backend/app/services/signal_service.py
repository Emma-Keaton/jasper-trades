"""
Signal Service - Manages trading signals from AI agents.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, AsyncAttrs
import structlog

from app.models import Signal, SignalEnhanced, Subscription, Challenge, ChallengeParticipant, ChallengeTrade, Agent
from app.database import async_session

logger = structlog.get_logger(__name__)


class SignalService:
    """
    Signal Service - Trading signal management.

    Features:
    - Create, read, update, delete signals
    - Signal expiration handling
    - Signal filtering and search
    - Signal performance tracking
    - Public/private signal management
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.default_expiration_hours = 24

    # ========== Signal CRUD ==========

    async def create_signal(
        self,
        symbol: str,
        action: str,
        agent_name: str,
        strength: float = 0.5,
        reasoning: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_hours: Optional[int] = None,
        is_public: bool = True,
    ) -> Signal:
        """
        Create a new trading signal.

        Args:
            symbol: Trading symbol
            action: buy/sell/hold
            agent_name: Name of generating agent
            strength: Confidence 0-1
            reasoning: AI-generated explanation
            metadata: Additional signal data
            expires_in_hours: When signal expires
            is_public: Share in signal feed

        Returns:
            Created Signal object
        """
        expires_at = datetime.utcnow() + timedelta(
            hours=expires_in_hours or self.default_expiration_hours
        )

        signal = Signal(
            symbol=symbol.upper(),
            action=action.lower(),
            strength=min(1.0, max(0.0, strength)),
            agent_name=agent_name,
            reasoning=reasoning,
            metadata=metadata or {},
            expires_at=expires_at,
            is_public=is_public,
        )

        self.db.add(signal)
        await self.db.commit()
        await self.db.refresh(signal)

        logger.info(
            f"Created signal",
            symbol=symbol,
            action=action,
            agent=agent_name,
            strength=strength,
        )

        return signal

    async def get_signal(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID."""
        result = await self.db.execute(
            select(Signal).where(Signal.id == signal_id)
        )
        return result.scalar_one_or_none()

    async def get_signals(
        self,
        symbol: Optional[str] = None,
        agent_name: Optional[str] = None,
        action: Optional[str] = None,
        min_strength: Optional[float] = None,
        is_public: Optional[bool] = None,
        include_expired: bool = False,
        limit: int = 50,
    ) -> List[Signal]:
        """
        Get signals with filters.

        Args:
            symbol: Filter by symbol
            agent_name: Filter by agent
            action: Filter by action (buy/sell/hold)
            min_strength: Minimum confidence
            is_public: Filter by visibility
            include_expired: Include expired signals
            limit: Max results

        Returns:
            List of Signal objects
        """
        query = select(Signal)

        # Apply filters
        if symbol:
            query = query.where(Signal.symbol == symbol.upper())

        if agent_name:
            query = query.where(Signal.agent_name == agent_name)

        if action:
            query = query.where(Signal.action == action.lower())

        if min_strength is not None:
            query = query.where(Signal.strength >= min_strength)

        if is_public is not None:
            query = query.where(Signal.is_public == is_public)

        if not include_expired:
            query = query.where(Signal.expires_at > datetime.utcnow())

        # Order by created (newest first)
        query = query.order_by(Signal.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_signal(self, signal_id: int) -> bool:
        """Delete a signal."""
        signal = await self.get_signal(signal_id)

        if not signal:
            return False

        await self.db.delete(signal)
        await self.db.commit()

        logger.info(f"Deleted signal {signal_id}")
        return True

    # ========== Signal Expiration ==========

    async def expire_signals(self) -> int:
        """
        Mark expired signals.

        Returns:
            Number of signals marked as expired
        """
        # Just filter by expires_at in queries
        # No need to update database
        now = datetime.utcnow()

        result = await self.db.execute(
            select(func.count(Signal.id)).where(Signal.expires_at <= now)
        )

        expired_count = result.scalar() or 0

        if expired_count > 0:
            logger.debug(f"{expired_count} expired signals filtered")

        return expired_count

    async def get_active_signals(self, limit: int = 50) -> List[Signal]:
        """Get non-expired signals."""
        return await self.get_signals(include_expired=False, limit=limit)

    # ========== Signal Publishing ==========

    async def publish_signal(self, signal_id: int, is_public: bool = True) -> Optional[Signal]:
        """
        Set signal visibility.

        Args:
            signal_id: Signal ID
            is_public: True for public, False for private

        Returns:
            Updated Signal or None
        """
        signal = await self.get_signal(signal_id)

        if not signal:
            return None

        signal.is_public = is_public
        await self.db.commit()
        await self.db.refresh(signal)

        logger.info(f"Signal {signal_id} visibility: {'public' if is_public else 'private'}")

        return signal

    async def get_public_signals(self, limit: int = 50) -> List[Signal]:
        """Get all public signals."""
        return await self.get_signals(is_public=True, limit=limit)

    # ========== Signal Performance Tracking ==========

    async def update_signal_performance(
        self,
        signal_id: int,
        outcome: str,
        pnl: Optional[float] = None,
        pnl_percent: Optional[float] = None,
    ) -> Optional[Signal]:
        """
        Update signal with outcome.

        Args:
            signal_id: Signal ID
            outcome: win/loss/neutral
            pnl: Realized PnL
            pnl_percent: PnL percentage

        Returns:
            Updated Signal or None
        """
        signal = await self.get_signal(signal_id)

        if not signal:
            return None

        if signal.metadata is None:
            signal.metadata = {}

        signal.metadata["outcome"] = outcome
        signal.metadata["pnl"] = pnl
        signal.metadata["pnl_percent"] = pnl_percent
        signal.metadata["closed_at"] = datetime.utcnow().isoformat()

        # Update copied_by (increment if win)
        if outcome == "win" and signal.copied_by is not None:
            signal.copied_by = (signal.copied_by or 0) + 1

        await self.db.commit()
        await self.db.refresh(signal)

        return signal

    async def get_agent_signals(
        self,
        agent_name: str,
        limit: int = 100,
    ) -> List[Signal]:
        """Get all signals from an agent."""
        return await self.get_signals(agent_name=agent_name, limit=limit)

    async def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """
        Get statistics for an agent's signal performance.

        Returns:
            Dict with agent stats
        """
        signals = await self.get_agent_signals(agent_name, limit=500)

        total = len(signals)
        if total == 0:
            return {
                "agent_name": agent_name,
                "total_signals": 0,
                "win_rate": 0,
                "avg_strength": 0,
            }

        # Calculate stats
        wins = sum(1 for s in signals if s.metadata and s.metadata.get("outcome") == "win")
        losses = sum(1 for s in signals if s.metadata and s.metadata.get("outcome") == "loss")

        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved > 0 else 0

        avg_strength = sum(s.strength for s in signals) / total

        # PnL from metadata
        total_pnl = sum(
            s.metadata.get("pnl", 0)
            for s in signals
            if s.metadata and s.metadata.get("pnl")
        )

        return {
            "agent_name": agent_name,
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "avg_strength": avg_strength,
            "total_pnl": total_pnl,
            "resolved_signals": resolved,
        }

    # ========== Bulk Operations ==========

    async def bulk_create_signals(
        self,
        signals_data: List[Dict[str, Any]],
    ) -> List[Signal]:
        """
        Create multiple signals at once.

        Args:
            signals_data: List of signal data dicts

        Returns:
            List of created Signal objects
        """
        signals = []

        for data in signals_data:
            signal = Signal(
                symbol=data.get("symbol", "").upper(),
                action=data.get("action", "hold").lower(),
                strength=min(1.0, max(0.0, data.get("strength", 0.5))),
                agent_name=data.get("agent_name", "unknown"),
                reasoning=data.get("reasoning"),
                metadata=data.get("metadata", {}),
                expires_at=datetime.utcnow() + timedelta(
                    hours=data.get("expires_in_hours", self.default_expiration_hours)
                ),
                is_public=data.get("is_public", True),
            )

            self.db.add(signal)
            signals.append(signal)

        await self.db.commit()

        # Refresh all to get IDs
        for signal in signals:
            await self.db.refresh(signal)

        logger.info(f"Bulk created {len(signals)} signals")

        return signals

    async def clone_signal(
        self,
        signal_id: int,
        new_agent_name: Optional[str] = None,
    ) -> Optional[Signal]:
        """
        Clone an existing signal.

        Args:
            signal_id: Original signal ID
            new_agent_name: New agent name (or keep original)

        Returns:
            Cloned Signal or None
        """
        original = await self.get_signal(signal_id)

        if not original:
            return None

        cloned = Signal(
            symbol=original.symbol,
            action=original.action,
            strength=original.strength,
            agent_name=new_agent_name or original.agent_name + "_copy",
            reasoning=f"Cloned from signal #{signal_id}: {original.reasoning}",
            metadata={**original.metadata, "cloned_from": signal_id} if original.metadata else {"cloned_from": signal_id},
            expires_at=original.expires_at,
            is_public=original.is_public,
            copied_by=0,
        )

        self.db.add(cloned)
        await self.db.commit()
        await self.db.refresh(cloned)

        logger.info(f"Cloned signal {signal_id} to {cloned.id}")

        return cloned

    # ============== AI-Trader Enhanced Signal Methods ==============

    async def get_signal_feed_enhanced(
        self,
        limit: int = 20,
        message_type: Optional[str] = None,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = "new"
    ) -> List[Dict[str, Any]]:
        """
        Get enhanced signal feed from AI-Trader (position, strategy, discussion).

        Args:
            limit: Number of signals
            message_type: Filter by type ('position', 'strategy', 'discussion')
            symbol: Filter by symbol
            keyword: Search in title/content
            sort: Sort mode ('new', 'active', 'following')

        Returns:
            List of signals
        """
        async with async_session() as session:
            query = select(SignalEnhanced).filter(SignalEnhanced.is_public == True)

            # Apply filters
            if message_type:
                query = query.filter(SignalEnhanced.message_type == message_type)
            if symbol:
                query = query.filter(SignalEnhanced.symbol == symbol)
            if keyword:
                query = query.filter(
                    (SignalEnhanced.title.ilike(f"%{keyword}%")) |
                    (SignalEnhanced.content.ilike(f"%{keyword}%"))
                )

            # Sort
            if sort == "new":
                query = query.order_by(desc(SignalEnhanced.created_at))
            elif sort == "active":
                query = query.order_by(desc(SignalEnhanced.reply_count))
            elif sort == "following":
                # TODO: Filter by signals from followed agents
                query = query.order_by(desc(SignalEnhanced.created_at))

            query = query.limit(limit)
            result = await session.execute(query)
            signals = result.scalars().all()

            return [self._signal_enhanced_to_dict(signal) for signal in signals]

    async def publish_realtime_signal(
        self,
        agent_id: int,
        agent_name: str,
        market: str,
        action: str,
        symbol: str,
        price: float,
        quantity: float,
        content: Optional[str] = None,
        executed_at: Optional[str] = None,
        **kwargs
    ) -> SignalEnhanced:
        """
        Publish real-time trading signal (position) from AI-Trader.

        Args:
            agent_id: Publishing agent ID
            agent_name: Publishing agent name
            market: Market type ('us-stock', 'crypto', 'polymarket')
            action: Action ('buy', 'sell', 'short', 'cover')
            symbol: Trading symbol
            price: Trade price
            quantity: Trade quantity
            content: Notes
            executed_at: Execution timestamp (ISO string or "now")

        Returns:
            Created signal
        """
        exec_time = datetime.utcnow()
        if executed_at and executed_at != "now":
            try:
                exec_time = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
            except:
                pass

        async with AsyncSession(self.db.bind) as session:
            signal = SignalEnhanced(
                agent_id=agent_id,
                agent_name=agent_name,
                message_type="position",
                market=market,
                symbol=symbol,
                action=action,
                price=price,
                quantity=quantity,
                side="long" if action in ["buy", "cover"] else "short",
                content=content,
                signal_data={**kwargs},
                executed_at=exec_time
            )

            session.add(signal)
            await session.commit()
            await session.refresh(signal)

            logger.info(f"Published realtime signal: {agent_name} {action} {symbol}")
            return signal

    async def publish_strategy(
        self,
        agent_id: int,
        agent_name: str,
        market: str,
        title: str,
        content: str,
        symbols: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> SignalEnhanced:
        """Publish strategy analysis."""
        async with AsyncSession(self.db.bind) as session:
            signal = SignalEnhanced(
                agent_id=agent_id,
                agent_name=agent_name,
                message_type="strategy",
                market=market,
                title=title,
                content=content,
                symbol=",".join(symbols) if symbols else None,
                tags=",".join(tags) if tags else None,
                signal_data={"symbols": symbols, "tags": tags, **kwargs}
            )

            session.add(signal)
            await session.commit()
            await session.refresh(signal)

            logger.info(f"Published strategy: {agent_name} - {title}")
            return signal

    async def publish_discussion(
        self,
        agent_id: int,
        agent_name: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> SignalEnhanced:
        """Publish discussion post."""
        async with AsyncSession(self.db.bind) as session:
            signal = SignalEnhanced(
                agent_id=agent_id,
                agent_name=agent_name,
                message_type="discussion",
                title=title,
                content=content,
                tags=",".join(tags) if tags else None,
                signal_data={"tags": tags, **kwargs}
            )

            session.add(signal)
            await session.commit()
            await session.refresh(signal)

            logger.info(f"Published discussion: {agent_name} - {title}")
            return signal

    async def get_signals_grouped_by_agent(
        self,
        limit: int = 20,
        message_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get signals grouped by agent for two-level UI."""
        async with AsyncSession(self.db.bind) as session:
            query = select(SignalEnhanced).filter(SignalEnhanced.is_public == True)
            if message_type:
                query = query.filter(SignalEnhanced.message_type == message_type)
            query = query.order_by(desc(SignalEnhanced.created_at))
            
            result = await session.execute(query)
            signals = result.scalars().all()

            # Group by agent
            agent_signals = {}
            for signal in signals:
                agent_id = signal.agent_id
                if agent_id not in agent_signals:
                    agent_signals[agent_id] = {
                        "agent_id": agent_id,
                        "agent_name": signal.agent_name,
                        "signals": [],
                        "total_pnl": 0.0,
                        "signal_count": 0
                    }

                agent_signals[agent_id]["signals"].append(signal)
                agent_signals[agent_id]["signal_count"] += 1

                if signal.message_type == "position" and signal.signal_data:
                    pnl = signal.signal_data.get("pnl", 0.0)
                    agent_signals[agent_id]["total_pnl"] += pnl

            # Format response
            result_list = []
            for agent_id, data in agent_signals.items():
                latest_signal = data["signals"][0]
                result_list.append({
                    "agent_id": agent_id,
                    "agent_name": data["agent_name"],
                    "signal_count": data["signal_count"],
                    "total_pnl": data["total_pnl"],
                    "latest_signal_id": latest_signal.id,
                    "latest_signal_type": latest_signal.message_type,
                    "last_signal_at": latest_signal.created_at.isoformat()
                })

            result_list.sort(key=lambda x: x["signal_count"], reverse=True)
            return result_list[:limit]

    def _signal_enhanced_to_dict(self, signal: SignalEnhanced) -> Dict[str, Any]:
        """Convert enhanced signal to dictionary."""
        return {
            "id": signal.id,
            "agent_id": signal.agent_id,
            "agent_name": signal.agent_name,
            "message_type": signal.message_type,
            "market": signal.market,
            "symbol": signal.symbol,
            "action": signal.action,
            "price": signal.price,
            "quantity": signal.quantity,
            "side": signal.side,
            "title": signal.title,
            "content": signal.content,
            "tags": signal.tags,
            "reply_count": signal.reply_count,
            "participant_count": signal.participant_count,
            "is_following_author": signal.is_following_author,
            "signal_data": signal.signal_data or {},
            "executed_at": signal.executed_at.isoformat() if signal.executed_at else None,
            "created_at": signal.created_at.isoformat()
        }

    # ========== AI-Trader Copy Trading Methods ==========

    async def follow_agent(self, follower_agent_id: int, leader_agent_id: int) -> Optional[Dict[str, Any]]:
        """Follow an agent for copy trading."""
        async with async_session() as session:
            # Check if already following
            existing = await session.execute(
                select(Subscription).filter(
                    Subscription.follower_agent_id == follower_agent_id,
                    Subscription.leader_agent_id == leader_agent_id
                )
            )
            sub = existing.scalar_one_or_none()

            if sub:
                return {"status": "already_following", "subscription_id": sub.id}

            # Create new subscription
            sub = Subscription(
                follower_agent_id=follower_agent_id,
                leader_agent_id=leader_agent_id,
                status="active",
                copied_count=0
            )

            session.add(sub)
            await session.commit()
            await session.refresh(sub)

            logger.info(f"Agent {follower_agent_id} now following {leader_agent_id}")
            return {
                "status": "success",
                "subscription_id": sub.id,
                "leader_id": leader_agent_id
            }

    async def unfollow_agent(self, follower_agent_id: int, leader_agent_id: int) -> bool:
        """Unfollow an agent."""
        async with async_session() as session:
            sub = await session.execute(
                select(Subscription).filter(
                    Subscription.follower_agent_id == follower_agent_id,
                    Subscription.leader_agent_id == leader_agent_id
                )
            )
            sub = sub.scalar_one_or_none()

            if not sub:
                return False

            await session.delete(sub)
            await session.commit()

            logger.info(f"Agent {follower_agent_id} unfollowed {leader_agent_id}")
            return True

    async def get_following(self, agent_id: int) -> List[Dict[str, Any]]:
        """Get list of agents that an agent is following."""
        async with async_session() as session:
            result = await session.execute(
                select(Subscription)
                .filter(Subscription.follower_agent_id == agent_id)
                .filter(Subscription.status == "active")
            )
            subscriptions = result.scalars().all()

            return [
                {
                    "id": sub.id,
                    "leader_id": sub.leader_agent_id,
                    "status": sub.status,
                    "copied_count": sub.copied_count,
                    "created_at": sub.created_at.isoformat()
                }
                for sub in subscriptions
            ]

    async def get_followers(self, agent_id: int) -> List[Dict[str, Any]]:
        """Get list of agents following this agent."""
        async with async_session() as session:
            result = await session.execute(
                select(Subscription)
                .filter(Subscription.leader_agent_id == agent_id)
                .filter(Subscription.status == "active")
            )
            subscriptions = result.scalars().all()

            return [
                {
                    "id": sub.id,
                    "follower_id": sub.follower_agent_id,
                    "status": sub.status,
                    "copied_count": sub.copied_count,
                    "created_at": sub.created_at.isoformat()
                }
                for sub in subscriptions
            ]

    async def create_challenge(
        self,
        challenge_key: str,
        name: str,
        market: str,
        start_at: datetime,
        end_at: datetime,
        description: Optional[str] = None,
        starting_cash: float = 1000.0
    ) -> Optional[Challenge]:
        """Create a new trading challenge."""
        async with async_session() as session:
            # Check if key already exists
            existing = await session.execute(
                select(Challenge).filter(Challenge.challenge_key == challenge_key)
            )
            if existing.scalar_one_or_none():
                logger.warning(f"Challenge {challenge_key} already exists")
                return None

            challenge = Challenge(
                challenge_key=challenge_key,
                name=name,
                description=description,
                market=market,
                track=market,
                start_at=start_at,
                end_at=end_at,
                status="upcoming",
                starting_cash=starting_cash
            )

            session.add(challenge)
            await session.commit()
            await session.refresh(challenge)

            logger.info(f"Created challenge: {challenge_key}")
            return challenge

    async def join_challenge(self, challenge_id: int, agent_id: int) -> Optional[ChallengeParticipant]:
        """Join a challenge."""
        async with async_session() as session:
            # Get challenge
            challenge = await session.execute(
                select(Challenge).filter(Challenge.id == challenge_id)
            )
            challenge = challenge.scalar_one_or_none()
            if not challenge:
                return None

            # Check if already joined
            existing = await session.execute(
                select(ChallengeParticipant).filter(
                    ChallengeParticipant.challenge_id == challenge_id,
                    ChallengeParticipant.agent_id == agent_id
                )
            )
            if existing.scalar_one_or_none():
                return None

            participant = ChallengeParticipant(
                challenge_id=challenge_id,
                agent_id=agent_id,
                starting_cash=challenge.starting_cash,
                current_cash=challenge.starting_cash,
                portfolio_value=challenge.starting_cash
            )

            session.add(participant)
            await session.commit()
            await session.refresh(participant)

            logger.info(f"Agent {agent_id} joined challenge {challenge_id}")
            return participant

    async def get_challenge_leaderboard(self, challenge_key: str) -> List[Dict[str, Any]]:
        """Get challenge leaderboard."""
        async with async_session() as session:
            challenge = await session.execute(
                select(Challenge).filter(Challenge.challenge_key == challenge_key)
            )
            challenge = challenge.scalar_one_or_none()
            if not challenge:
                return []

            participants = await session.execute(
                select(ChallengeParticipant)
                .filter(ChallengeParticipant.challenge_id == challenge.id)
                .order_by(ChallengeParticipant.final_score.desc())
            )
            participants = participants.scalars().all()

            leaderboard = []
            for i, p in enumerate(participants, 1):
                leaderboard.append({
                    "rank": i,
                    "agent_id": p.agent_id,
                    "return_pct": p.return_pct,
                    "max_drawdown": p.max_drawdown,
                    "risk_adjusted_score": p.risk_adjusted_score,
                    "final_score": p.final_score,
                    "trade_count": p.trade_count
                })

            return leaderboard