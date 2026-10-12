"""
Trading endpoints - Execute trades, get positions, view history.
Sends Telegram notifications for trade executions
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, model_validator
import structlog
import asyncio
from datetime import datetime

from app.database import get_db
from app.models import Trade, Position
from app.config import settings
from app.services.portfolio_service import PortfolioService
from app.services.valuation_service import ValuationService
from app.services.circuit_breaker import get_circuit_breaker
from app.agents import agent_registry
from app.brokers import broker_registry
from app.brokers.router import broker_router
from app.brokers.tiger_service import _is_chinese_symbol

logger = structlog.get_logger(__name__)

router = APIRouter()


from app.device_auth import require_device_id

def _trading_asset_class(symbol: str) -> str:
    """Route-aware asset class: 'cn' for Chinese codes, 'us-stocks' for US tickers."""
    symbol = str(symbol or "").strip()
    if _is_chinese_symbol(symbol):
        return "cn"
    detected = broker_router.detect_asset_class(symbol)
    return "us-stocks" if detected == "stocks" else detected


class ExecuteTradeRequest(BaseModel):
    """Body for `POST /api/v1/trading/execute`.

    This was a set of bare query parameters while the frontend sent a JSON body
    (`type`/`shares`), so FastAPI ignored the body entirely and every call from
    the UI returned 422 - the primary trade button could not place an order.

    The frontend field names are preserved (`type`, `shares`) because that is what
    is on the wire. `side` and `quantity` are accepted as aliases so a caller
    written against the documented query names also works.
    """

    symbol: str
    # Accept either name. `type` is what the frontend sends.
    type: Optional[str] = Field(
        default=None, description="'buy' or 'sell'. Alias: side."
    )
    side: Optional[str] = Field(
        default=None, description="Alias for `type`."
    )
    shares: Optional[float] = Field(
        default=None, gt=0, description="Quantity. Alias: quantity."
    )
    quantity: Optional[float] = Field(
        default=None, gt=0, description="Alias for `shares`."
    )
    order_type: str = "market"
    portfolio_id: Optional[int] = None
    broker: str = "auto"
    # Optional client-supplied limit price. The gate resolves a market price
    # when omitted.
    price: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _require_side_and_quantity(self):
        if not (self.type or self.side):
            raise ValueError("one of 'type' or 'side' is required")
        if self.shares is None and self.quantity is None:
            raise ValueError("one of 'shares' or 'quantity' is required")
        return self

    @property
    def resolved_side(self) -> str:
        return (self.type or self.side or "").strip().lower()

    @property
    def resolved_quantity(self) -> float:
        return float(self.shares if self.shares is not None else self.quantity)


@router.post("/execute")
async def execute_trade(
    request: ExecuteTradeRequest,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a trade.

    Routes through the unified trade gate: practice mode executes in the
    universal paper engine; live mode only with a live-configured device AND a
    connected non-paper broker.
    """
    symbol = request.symbol.strip().upper()
    side = request.resolved_side
    quantity = request.resolved_quantity
    order_type = request.order_type
    portfolio_id = request.portfolio_id
    broker = request.broker

    try:
        from app.services import trade_gate

        device_id = require_device_id(x_device_id)
        mode = await trade_gate.resolve_mode(db, device_id)
        live_asset_class = _trading_asset_class(symbol)

        # Resolve a market price (needed for the gate + paper fills).
        price = request.price or await ValuationService().get_price(symbol)

        gate = await trade_gate.check_prerequisites(
            db,
            device_id,
            symbol=symbol,
            side=side,
            qty=quantity,
            price=price or 0.0,
            intent=mode,
            asset_class=live_asset_class,
            broker=broker,
            portfolio_id=portfolio_id,
            route="execute",
        )
        if not gate["passed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Trade blocked: {trade_gate.describe_failures(gate)}",
            )

        # ----- Paper mode: universal paper engine -----
        if mode == "paper":
            if not price or price <= 0:
                raise HTTPException(status_code=400, detail="Could not resolve a market price for paper fill")
            result = await trade_gate.execute_paper(
                device_id=device_id,
                symbol=symbol.upper(),
                side=side.lower(),
                qty=quantity,
                price=price,
                asset_class=live_asset_class,
                agent_name="manual",
                reasoning=f"order_type={order_type}, broker={broker}",
            )
            if result.get("error"):
                raise HTTPException(status_code=400, detail=result)
            return {
                "status": "success",
                "mode": "paper",
                "trade_id": None,
                "broker": "paper",
                "message": f"Paper {side} {quantity} {symbol} @ ${price:.4g}",
                **result,
            }

        # ----- Live mode -----
        # Check circuit breaker first (live guardian)
        circuit = get_circuit_breaker()
        if not circuit.can_trade():
            logger.warning(
                f"Trade blocked by circuit breaker",
                symbol=symbol,
                side=side,
                quantity=quantity,
                reason=circuit.trigger_reason,
            )
            raise HTTPException(
                status_code=423,  # Locked
                detail=f"Trading halted: {circuit.trigger_reason}",
            )

        # ----- Live CN/US via per-device funded broker (Tiger preferred) -----
        from app.brokers.tiger_service import place_tiger_live_order, tiger_configured

        tiger_result = None
        if live_asset_class == "cn":
            tiger_result = await place_tiger_live_order(
                db, device_id, symbol=symbol, side=side, quantity=quantity,
                order_type=order_type, asset_class="cn",
            )
        elif live_asset_class in ("stocks", "us-stocks") and await tiger_configured(db, device_id):
            tiger_result = await place_tiger_live_order(
                db, device_id, symbol=symbol, side=side, quantity=quantity,
                order_type=order_type, asset_class="us-stocks",
            )

        if tiger_result:
            portfolio_service = PortfolioService(db)

            if portfolio_id is None:
                portfolios = await portfolio_service.get_portfolios(device_id)
                if not portfolios:
                    portfolio = await portfolio_service.create_portfolio(
                        name="Default",
                        initial_cash=settings.UNIVERSAL_PAPER_CAPITAL,
                        is_paper=True,
                        # `device_id` is NOT NULL. It was omitted here, so on a
                        # fresh database this raised IntegrityError and the
                        # request 500'd. Guarded by `if not portfolios:`, so it
                        # only ever fired on first boot against an empty table.
                        device_id=device_id,
                    )
                    portfolio_id = portfolio.id
                else:
                    portfolio_id = portfolios[0].id

            filled_price = float(tiger_result.get("filled_price") or price or 0)
            trade = Trade(
                symbol=symbol,
                side=side.lower(),
                quantity=quantity,
                price=filled_price,
                order_type=order_type,
                status="filled",
                broker="tiger",
                broker_order_id=tiger_result.get("order_id"),
                agent_name="tiger-live",
                created_at=datetime.utcnow(),
            )
            db.add(trade)
            await db.commit()
            await db.refresh(trade)

            try:
                if side.lower() == "buy":
                    await portfolio_service.add_position(
                        portfolio_id=portfolio_id,
                        symbol=symbol,
                        quantity=quantity,
                        price=filled_price,
                    )
                    await portfolio_service.update_cash(
                        portfolio_id=portfolio_id,
                        amount=-quantity * filled_price,
                        description=f"Buy {quantity} {symbol} (Tiger)",
                    )
                else:
                    p_result = await portfolio_service.reduce_position(
                        portfolio_id=portfolio_id,
                        symbol=symbol,
                        quantity=quantity,
                        price=filled_price,
                    )
                    if not p_result.get("error"):
                        await portfolio_service.update_cash(
                            portfolio_id=portfolio_id,
                            amount=quantity * filled_price,
                            description=f"Sell {quantity} {symbol} (Tiger)",
                        )
            except Exception as e:  # noqa: BLE001
                logger.warning("Portfolio bookkeeping failed for Tiger trade", error=str(e))

            return {
                "status": "success",
                "mode": "live",
                "trade_id": trade.id,
                "broker_order_id": trade.broker_order_id,
                "broker": "tiger",
                "message": tiger_result.get("message", f"Executed {side} {quantity} {symbol}"),
                **tiger_result,
            }

        # ----- Live mode: existing execution-agent path (crypto/forex/solana/trove) -----
        # Initialize brokers if needed
        execution_agent = agent_registry.get("execution")

        if not execution_agent:
            raise HTTPException(status_code=500, detail="Execution agent not available")

        # Ensure brokers are initialized
        if not execution_agent._brokers_initialized:
            await execution_agent.initialize_brokers()

        # Get default portfolio
        portfolio_service = PortfolioService(db)

        if portfolio_id is None:
            portfolios = await portfolio_service.get_portfolios(device_id)
            if not portfolios:
                # Create default portfolio. `device_id` is NOT NULL; omitting it
                # raised IntegrityError on a fresh database.
                portfolio = await portfolio_service.create_portfolio(
                    name="Default",
                    initial_cash=settings.UNIVERSAL_PAPER_CAPITAL,
                    is_paper=True,
                    device_id=device_id,
                )
                portfolio_id = portfolio.id
            else:
                portfolio_id = portfolios[0].id

        # Create order
        trade = await execution_agent.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
        )

        # Submit to broker
        trade = await execution_agent.submit_to_broker(trade, broker)

        if trade.status == "submitted":
            # Update portfolio position
            portfolio = await portfolio_service.get_portfolio(portfolio_id)
            result = {}

            if side.lower() == "buy":
                # Add position
                await portfolio_service.add_position(
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    quantity=quantity,
                    price=trade.price or 0,
                )

                # Deduct cash (estimated)
                estimated_cost = quantity * (trade.price or 0)
                if estimated_cost > 0:
                    await portfolio_service.update_cash(
                        portfolio_id=portfolio_id,
                        amount=-estimated_cost,
                        description=f"Buy {quantity} {symbol}",
                    )
            else:
                # Reduce position
                result = await portfolio_service.reduce_position(
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    quantity=quantity,
                    price=trade.price or 0,
                )

                # Add cash (estimated)
                if not result.get("error"):
                    estimated_proceeds = quantity * (trade.price or 0)
                    if estimated_proceeds > 0:
                        await portfolio_service.update_cash(
                            portfolio_id=portfolio_id,
                            amount=estimated_proceeds,
                            description=f"Sell {quantity} {symbol}",
                        )

            # Save trade to DB
            db.add(trade)
            await db.commit()
            await db.refresh(trade)

            # Send Telegram notification (async, non-blocking)
            from app.config import settings
            if settings.TELEGRAM_BOT_TOKEN:
                asyncio.create_task(_send_trade_telegram_notification(
                    trade, 
                    device_id,
                    db
                ))

            return {
                "status": "success",
                "trade_id": trade.id,
                "broker_order_id": trade.broker_order_id,
                "broker": trade.broker,
                "message": f"Executed {side} {quantity} {symbol} @ ${trade.price or 'market'}",
                "realized_pnl": result.get("realized_pnl", 0) if side.lower() == "sell" else None,
            }
        else:
            return {
                "status": "rejected",
                "reason": "Order rejected by broker",
                "trade": {
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    portfolio_id: Optional[int] = None,
    include_empty: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get current positions."""
    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

    # Get default portfolio
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios(device_id)
        if not portfolios:
            return {"positions": []}
        portfolio_id = portfolios[0].id

    # Get positions
    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty)

    # Update with current prices
    if positions:
        symbols = [p.symbol for p in positions]
        prices = await valuation_service.get_prices(symbols)
        await portfolio_service.update_position_prices(portfolio_id, prices)

        # Refresh positions
        positions = await portfolio_service.get_all_positions(portfolio_id, include_empty)

    return {
        "portfolio_id": portfolio_id,
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
            for p in positions if p.quantity > 0 or include_empty
        ]
    }


@router.get("/positions/{symbol}")
async def get_position(
    symbol: str,
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get single position details."""
    portfolio_service = PortfolioService(db)
    valuation_service = ValuationService()

    # Get default portfolio
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios(device_id)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id

    # Get position
    position = await portfolio_service.get_position(portfolio_id, symbol)

    if not position:
        raise HTTPException(status_code=404, detail=f"No position found for {symbol}")

    # Update price
    price = await valuation_service.get_price(symbol)
    if price:
        await portfolio_service.update_position_prices(
            portfolio_id,
            {symbol: price},
        )
        position = await portfolio_service.get_position(portfolio_id, symbol)

    return {
        "symbol": position.symbol,
        "quantity": position.quantity,
        "avg_price": position.avg_price,
        "current_price": position.current_price,
        "market_value": position.market_value,
        "unrealized_pnl": position.unrealized_pnl,
        "unrealized_pnl_percent": position.unrealized_pnl_percent,
    }


@router.delete("/positions/{symbol}")
async def close_position(
    symbol: str,
    portfolio_id: Optional[int] = None,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Close a position (market sell)."""
    device_id = require_device_id(x_device_id)
    portfolio_service = PortfolioService(db)

    # Get default portfolio
    if portfolio_id is None:
        portfolios = await portfolio_service.get_portfolios(device_id)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")
        portfolio_id = portfolios[0].id

    # Get current price
    valuation_service = ValuationService()
    current_price = await valuation_service.get_price(symbol)

    if not current_price:
        raise HTTPException(status_code=500, detail=f"Could not fetch price for {symbol}")

    # Execute market sell
    position = await portfolio_service.get_position(portfolio_id, symbol)

    if not position or position.quantity <= 0:
        raise HTTPException(status_code=404, detail=f"No position found for {symbol}")

    # Submit sell order
    execution_agent = agent_registry.get("execution")

    if not execution_agent:
        raise HTTPException(status_code=500, detail="Execution agent not available")

    trade = await execution_agent.create_order(
        symbol=symbol,
        side="sell",
        quantity=position.quantity,
        order_type="market",
    )

    trade = await execution_agent.submit_to_broker(trade)

    if trade.status != "submitted":
        raise HTTPException(status_code=500, detail="Failed to submit sell order")

    # Update position
    result = await portfolio_service.reduce_position(
        portfolio_id=portfolio_id,
        symbol=symbol,
        quantity=position.quantity,
        price=current_price,
    )

    # Add cash
    proceeds = position.quantity * current_price
    await portfolio_service.update_cash(
        portfolio_id=portfolio_id,
        amount=proceeds,
        description=f"Close position {symbol}",
    )

    # Save trade
    db.add(trade)
    await db.commit()

    realized_pnl = result.get("realized_pnl", 0) or 0

    # Announce the close. `notify_trade_closed` existed but was never called, so
    # closing a position was silent. Fire-and-forget: a Telegram failure must not
    # roll back or delay a completed close.
    #
    # This block used `position.average_price`, but the column is `avg_price`
    # (models.py). It raised AttributeError *after* reduce_position,
    # update_cash and the trade commit had all succeeded, so every close returned
    # HTTP 500 while the books had already changed: the client saw a failure and
    # the position was gone. The arithmetic is also computed defensively, so a
    # malformed position cannot turn a completed close into a 500.
    from app.services.notification_hub import hub

    entry_price = float(position.avg_price or 0.0)
    closed_qty = float(position.quantity or 0.0)
    cost_basis = entry_price * closed_qty
    pnl_percent = (realized_pnl / cost_basis * 100) if cost_basis else 0.0

    hub.trade_closed_soon(
        device_id,
        {
            "symbol": symbol,
            "side": "sell",
            "quantity": closed_qty,
            "price": current_price,
            "entry_price": entry_price,
            "pnl": realized_pnl,
            "pnl_percent": round(pnl_percent, 4),
            "status": trade.status,
        },
    )

    return {
        "status": "success",
        "symbol": symbol,
        "quantity_closed": position.quantity,
        "price": current_price,
        "proceeds": proceeds,
        "realized_pnl": realized_pnl,
    }


@router.get("/history")
async def get_trade_history(
    symbol: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    status: Optional[str] = None,
    portfolio_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get trade history."""
    from sqlalchemy import select

    query = select(Trade).order_by(Trade.created_at.desc()).limit(limit)

    if symbol:
        query = query.where(Trade.symbol == symbol.upper())

    if status:
        query = query.where(Trade.status == status)

    result = await db.execute(query)
    trades = list(result.scalars().all())

    return {
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "order_type": t.order_type,
                "status": t.status,
                "broker": t.broker,
                "broker_order_id": t.broker_order_id,
                "agent_name": t.agent_name,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ]
    }


@router.post("/{trade_id}/cancel")
async def cancel_trade(
    trade_id: int,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or submitted order.

    `ExecutionAgent.cancel_order` has existed for a while and had no route to reach
    it, so the frontend's `cancelTrade(tradeId)` had nothing to call.

    Scoped to the calling device through the portfolio: `Trade` carries only
    `portfolio_id`, so the ownership check has to join. Someone else's trade returns
    404 rather than 403 - "forbidden" would confirm the id exists.
    """
    from app.agents import agent_registry
    from app.models import Portfolio
    from sqlalchemy import select

    device_id = require_device_id(x_device_id)

    result = await db.execute(
        select(Trade)
        .join(Portfolio, Trade.portfolio_id == Portfolio.id)
        .where(Trade.id == trade_id, Portfolio.device_id == device_id)
    )
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status == "filled":
        raise HTTPException(
            status_code=409,
            detail="A filled trade cannot be cancelled",
        )

    agent = agent_registry.get("execution")
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Execution agent unavailable; cannot cancel right now",
        )

    if not getattr(agent, "_brokers_initialized", False):
        await agent.initialize_brokers()

    cancelled = await agent.cancel_order(trade)
    if not cancelled:
        # cancel_order never raises; a False means the venue refused or there was no
        # venue to ask. The row keeps its current status so the UI shows reality.
        return {
            "id": trade.id,
            "status": trade.status,
            "cancelled": False,
            "detail": "The venue did not accept the cancellation; order status unchanged",
        }

    trade.status = "cancelled"
    await db.commit()
    await db.refresh(trade)

    return {"id": trade.id, "status": trade.status, "cancelled": True}


@router.get("/history/{trade_id}")
async def get_trade_details(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific trade."""
    from sqlalchemy import select

    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "order_type": trade.order_type,
        "status": trade.status,
        "broker": trade.broker,
        "broker_order_id": trade.broker_order_id,
        "agent_name": trade.agent_name,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "pnl": trade.pnl,
        "pnl_percent": trade.pnl_percent,
        "created_at": trade.created_at.isoformat(),
        "updated_at": trade.updated_at.isoformat(),
    }


async def _send_trade_telegram_notification(trade: Trade, device_id: str, db: AsyncSession):
    """Send Telegram notification for executed trade"""
    from app.config import settings
    from app.services.telegram_bot_service import get_telegram_bot_service
    from app.models import TelegramUser
    from sqlalchemy import select
    import structlog
    logger = structlog.get_logger(__name__)
    
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    
    # Get user's chat_id from database
    result = await db.execute(
        select(TelegramUser).where(
            TelegramUser.device_id == device_id,
            TelegramUser.is_verified == True,
            TelegramUser.trade_notifications_enabled == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.debug(f"No verified Telegram user found for device {device_id[:8]}***")
        return
    
    trade_data = {
        "action": "BUY" if trade.side == "buy" else "SELL",
        "symbol": trade.symbol,
        "shares": trade.quantity,
        "price": trade.price or 0,
        "total": trade.quantity * (trade.price or 0),
        "agent": trade.agent_name or "AI",
        "timestamp": trade.created_at.strftime("%Y-%m-%d %H:%M") if trade.created_at else "Now"
    }
    
    bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
    await bot_service.send_trade_notification(user.chat_id, trade_data)


@router.get("/brokers/status")
async def get_brokers_status():
    """Get status of all connected brokers."""
    return {
        "brokers": broker_registry.get_stats(),
        "registry": str(broker_registry),
    }