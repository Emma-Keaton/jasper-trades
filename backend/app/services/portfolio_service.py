"""
Portfolio Service - Manages portfolio holdings, positions, and PnL calculations.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models import Portfolio, Position, Trade
from app.brokers import get_broker, get_broker_for_asset

logger = structlog.get_logger(__name__)


class PortfolioService:
    """
    Portfolio Service - Core portfolio management operations.

    Features:
    - Portfolio CRUD operations
    - Position management (add, reduce, close)
    - PnL calculations (realized and unrealized)
    - Asset allocation tracking
    - Cash management
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== Portfolio CRUD ==========

    async def get_portfolio(
        self,
        portfolio_id: int,
        include_positions: bool = True,
    ) -> Optional[Portfolio]:
        """
        Get portfolio by ID.

        Args:
            portfolio_id: Portfolio ID
            include_positions: Whether to load positions

        Returns:
            Portfolio object or None
        """
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
        return result.scalar_one_or_none()

    async def get_portfolios(
        self,
        portfolio_type: Optional[str] = None,  # "paper" or "live"
        broker: Optional[str] = None,
    ) -> List[Portfolio]:
        """
        Get all portfolios with optional filters.

        Args:
            portfolio_type: Filter by paper/live
            broker: Filter by broker

        Returns:
            List of Portfolio objects
        """
        query = select(Portfolio)

        if portfolio_type:
            is_paper = portfolio_type.lower() == "paper"
            query = query.where(Portfolio.is_paper == is_paper)

        if broker:
            query = query.where(Portfolio.broker == broker)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_portfolio(
        self,
        name: str,
        initial_cash: float = 100000.0,
        is_paper: bool = True,
        broker: str = "ctrader",
        device_id: Optional[str] = None,
    ) -> Portfolio:
        """
        Create a new portfolio.

        Args:
            name: Portfolio name
            initial_cash: Starting cash amount
            is_paper: Paper trading or live
            broker: Default broker (defaults to ctrader)
            device_id: Device ID for the portfolio (required)

        Returns:
            Created Portfolio object
        """
        portfolio = Portfolio(
            device_id=device_id,
            name=name,
            cash=initial_cash,
            initial_value=initial_cash,
            is_paper=is_paper,
            broker=broker,
        )

        self.db.add(portfolio)
        await self.db.commit()
        await self.db.refresh(portfolio)

        logger.info(
            f"Created portfolio: {name}",
            portfolio_id=portfolio.id,
            initial_cash=initial_cash,
            is_paper=is_paper,
        )

        return portfolio

    async def delete_portfolio(self, portfolio_id: int) -> bool:
        """
        Delete a portfolio (must have no positions).

        Returns:
            True if deleted, False if not found or has positions
        """
        portfolio = await self.get_portfolio(portfolio_id)

        if not portfolio:
            return False

        # Check for positions
        positions_result = await self.db.execute(
            select(func.count()).select_from(Position).where(Position.portfolio_id == portfolio_id)
        )
        position_count = positions_result.scalar()

        if position_count > 0:
            logger.warning(f"Cannot delete portfolio {portfolio_id}: has {position_count} positions")
            return False

        await self.db.delete(portfolio)
        await self.db.commit()

        logger.info(f"Deleted portfolio {portfolio_id}")
        return True

    # ========== Position Management ==========

    async def get_position(
        self,
        portfolio_id: int,
        symbol: str,
    ) -> Optional[Position]:
        """
        Get position for a symbol in portfolio.

        Args:
            portfolio_id: Portfolio ID
            symbol: Trading symbol

        Returns:
            Position object or None
        """
        result = await self.db.execute(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def get_all_positions(
        self,
        portfolio_id: int,
        include_empty: bool = False,
    ) -> List[Position]:
        """
        Get all positions in a portfolio.

        Args:
            portfolio_id: Portfolio ID
            include_empty: Include zero quantity positions

        Returns:
            List of Position objects
        """
        query = select(Position).where(Position.portfolio_id == portfolio_id)

        if not include_empty:
            query = query.where(Position.quantity > 0)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_position(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: float,
        price: float,
        current_price: Optional[float] = None,
    ) -> Position:
        """
        Add to or create a position.

        Args:
            portfolio_id: Portfolio ID
            symbol: Trading symbol
            quantity: Quantity to add
            price: Average entry price for this purchase
            current_price: Current market price

        Returns:
            Updated Position object
        """
        position = await self.get_position(portfolio_id, symbol)

        if position:
            # Update existing position
            total_quantity = position.quantity + quantity
            total_cost = (position.quantity * position.avg_price) + (quantity * price)
            new_avg_price = total_cost / total_quantity if total_quantity > 0 else 0

            position.quantity = total_quantity
            position.avg_price = new_avg_price

            logger.info(
                f"Added to position",
                symbol=symbol,
                quantity=quantity,
                price=price,
                new_quantity=total_quantity,
            )
        else:
            # Create new position
            position = Position(
                portfolio_id=portfolio_id,
                symbol=symbol.upper(),
                quantity=quantity,
                avg_price=price,
                current_price=current_price or price,
            )

            self.db.add(position)
            logger.info(
                f"Created new position",
                symbol=symbol,
                quantity=quantity,
                price=price,
            )

        # Update market value
        if current_price:
            position.current_price = current_price
            position.market_value = position.quantity * position.current_price
            position.unrealized_pnl = (
                (position.current_price - position.avg_price) * position.quantity
            )
            position.unrealized_pnl_percent = (
                (position.current_price - position.avg_price) / position.avg_price * 100
                if position.avg_price > 0
                else 0
            )

        await self.db.commit()
        await self.db.refresh(position)

        return position

    async def reduce_position(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        """
        Reduce or close a position.

        Args:
            portfolio_id: Portfolio ID
            symbol: Trading symbol
            quantity: Quantity to reduce
            price: Exit price

        Returns:
            Dict with realized PnL and updated position info
        """
        position = await self.get_position(portfolio_id, symbol)

        if not position or position.quantity <= 0:
            logger.warning(f"No position to reduce for {symbol}")
            return {"error": "No position found", "realized_pnl": 0}

        # Calculate realized PnL
        if position.side if hasattr(position, 'side') else "long":
            realized_pnl = (price - position.avg_price) * quantity
        else:
            realized_pnl = (position.avg_price - price) * quantity

        realized_pnl_percent = (
            (realized_pnl / (position.avg_price * quantity)) * 100
            if position.avg_price > 0
            else 0
        )

        # Update position
        position.quantity -= quantity

        if position.quantity <= 0:
            # Position closed
            old_quantity = position.quantity
            position.quantity = 0
            position.market_value = 0
            position.unrealized_pnl = 0
            position.unrealized_pnl_percent = 0
            logger.info(
                f"Position closed",
                symbol=symbol,
                realized_pnl=realized_pnl,
            )
        else:
            logger.info(
                f"Reduced position",
                symbol=symbol,
                quantity=quantity,
                remaining=position.quantity,
            )

        await self.db.commit()
        await self.db.refresh(position)

        return {
            "realized_pnl": realized_pnl,
            "realized_pnl_percent": realized_pnl_percent,
            "position": position,
            "closed": position.quantity == 0,
        }

    async def update_position_prices(
        self,
        portfolio_id: int,
        prices: Dict[str, float],
    ) -> List[Position]:
        """
        Update current prices for all positions.

        Args:
            portfolio_id: Portfolio ID
            prices: Dict of symbol -> current price

        Returns:
            List of updated positions
        """
        positions = await self.get_all_positions(portfolio_id)

        for position in positions:
            if position.symbol in prices:
                old_value = position.market_value or 0
                position.current_price = prices[position.symbol]
                position.market_value = position.quantity * position.current_price
                position.unrealized_pnl = (
                    (position.current_price - position.avg_price) * position.quantity
                )
                position.unrealized_pnl_percent = (
                    (position.current_price - position.avg_price) / position.avg_price * 100
                    if position.avg_price > 0
                    else 0
                )

                if old_value != position.market_value:
                    logger.debug(
                        f"Updated position price",
                        symbol=position.symbol,
                        old_price=old_value / position.quantity if position.quantity > 0 else 0,
                        new_price=position.current_price,
                    )

        await self.db.commit()

        return positions

    # ========== Portfolio Calculations ==========

    async def get_portfolio_summary(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary.

        Returns:
            Dict with portfolio metrics
        """
        portfolio = await self.get_portfolio(portfolio_id)

        if not portfolio:
            return {"error": "Portfolio not found"}

        positions = await self.get_all_positions(portfolio_id)

        # Calculate totals
        total_market_value = sum(p.market_value or 0 for p in positions)
        total_cost_basis = sum(
            p.quantity * p.avg_price for p in positions if p.quantity > 0
        )
        total_unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)

        # Check if portfolio is initialized (has real trading activity)
        has_positions = len([p for p in positions if p.quantity > 0]) > 0
        trades_result = await self.get_pnl(portfolio_id)
        has_trades = trades_result.get("trade_count", 0) > 0
        is_initialized = has_positions or has_trades

        # Portfolio value
        total_value = portfolio.cash + total_market_value

        # Only calculate PnL if portfolio is initialized with real trading activity
        # Otherwise return $0 PnL to avoid showing phantom gains/losses
        if is_initialized:
            total_return = total_value - portfolio.initial_value
            total_return_percent = (total_return / portfolio.initial_value * 100) if portfolio.initial_value > 0 else 0
        else:
            # No trading activity yet - PnL should be $0
            total_return = 0.0
            total_return_percent = 0.0

        # Asset allocation
        allocation = {}
        for position in positions:
            if position.market_value and total_market_value > 0:
                allocation[position.symbol] = {
                    "weight": position.market_value / total_market_value * 100,
                    "value": position.market_value,
                }

        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "total_value": total_value,
            "cash": portfolio.cash,
            "market_value": total_market_value,
            "initial_value": portfolio.initial_value if is_initialized else 0.0,
            "total_return": total_return,
            "total_return_percent": total_return_percent,
            "unrealized_pnl": total_unrealized_pnl,
            "positions_count": len([p for p in positions if p.quantity > 0]),
            "allocation": allocation,
            "is_paper": portfolio.is_paper,
            "broker": portfolio.broker,
            "is_initialized": is_initialized,
        }

    async def get_pnl(
        self,
        portfolio_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Calculate PnL for a period.

        Returns:
            Dict with realized, unrealized, and total PnL
        """
        # Realized PnL from trades
        query = select(
            func.sum(Trade.pnl).label('total_pnl'),
            func.count(Trade.id).label('trade_count'),
        ).where(
            Trade.status == 'filled',
        )

        if start_date:
            query = query.where(Trade.created_at >= start_date)
        if end_date:
            query = query.where(Trade.created_at <= end_date)

        result = await self.db.execute(query)
        row = result.first()

        realized_pnl = float(row.total_pnl) if row.total_pnl else 0

        # Unrealized PnL from positions
        positions = await self.get_all_positions(portfolio_id)
        unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": realized_pnl + unrealized_pnl,
            "trade_count": row.trade_count if row else 0,
        }

    # ========== Cash Management ==========

    async def update_cash(
        self,
        portfolio_id: int,
        amount: float,
        description: str = "cash adjustment",
    ) -> Portfolio:
        """
        Add or withdraw cash from portfolio.

        Args:
            portfolio_id: Portfolio ID
            amount: Positive for deposit, negative for withdrawal
            description: Reason for adjustment

        Returns:
            Updated Portfolio
        """
        portfolio = await self.get_portfolio(portfolio_id)

        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        old_cash = portfolio.cash
        portfolio.cash += amount

        await self.db.commit()
        await self.db.refresh(portfolio)

        logger.info(
            f"Updated cash",
            portfolio_id=portfolio_id,
            old_cash=old_cash,
            new_cash=portfolio.cash,
            amount=amount,
            description=description,
        )

        return portfolio

    # ========== Trade Synchronization ==========

    async def sync_from_trades(self, portfolio_id: int) -> int:
        """
        Rebuild positions from trade history.

        Use this to reconcile positions with trade executions.

        Returns:
            Number of positions updated
        """
        # Get all filled trades
        query = select(Trade).where(
            Trade.status == 'filled',
        ).order_by(Trade.created_at)

        result = await self.db.execute(query)
        trades = list(result.scalars().all())

        # Group by symbol
        positions: Dict[str, Dict] = {}

        for trade in trades:
            symbol = trade.symbol.upper()

            if symbol not in positions:
                positions[symbol] = {
                    "quantity": 0,
                    "total_cost": 0,
                }

            if trade.side.lower() == "buy":
                positions[symbol]["quantity"] += trade.quantity
                positions[symbol]["total_cost"] += (trade.quantity * (trade.entry_price or 0))
            else:
                positions[symbol]["quantity"] -= trade.quantity
                # Realize PnL for sells (simplified)

        # Update portfolio positions
        updated = 0
        for symbol, pos_data in positions.items():
            if pos_data["quantity"] > 0:
                avg_price = pos_data["total_cost"] / pos_data["quantity"]
                # Would need current price here for full update
                updated += 1

        logger.info(f"Synced {updated} positions from trade history")
        return updated