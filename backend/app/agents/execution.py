"""
Execution Agent
Order routing, broker submission, and fill tracking.

This is the only place orders are created and dispatched. The rest of the agent
pipeline never touches raw HTTP or WebSocket details.

History worth knowing, because it caused a long outage: this class previously
existed with `create_order`, `submit_to_broker` and `initialize_brokers`, and
those methods were dropped in a refactor while three call sites kept using them.
Nothing caught it, because no test executed an order. Every live trade through
`api/v1/trading.py`, `copytrade_service` and `signal_sources/ingest` raised
`AttributeError` at the first call. `tests/test_execution_agent.py` now exercises
the whole path so a removal cannot pass silently again.
"""

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from app.agents.base import BaseAgent
from app.brokers import broker_registry
from app.brokers.router import broker_router
from app.models import Trade

logger = structlog.get_logger(__name__)

#: Side values a broker will accept. Rejecting anything else locally is far
#: cheaper than sending it and having the venue reject it.
VALID_SIDES = ("buy", "sell", "long", "short")

#: Order types routed to a venue. A typo here would otherwise be forwarded and
#: rejected remotely, after the order had been built.
VALID_ORDER_TYPES = ("market", "limit", "stop", "stop_limit")


class ExecutionAgent(BaseAgent):
    """
    Execution Agent - Order routing and broker submission.

    Responsibilities:
    - Translate risk-approved signals into broker orders
    - Route to the correct venue (auto / paper / binance / solana / trove)
    - Track fill status and report back to the ledger
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Execution",
            model="execution-engine",
            config=config or {},
        )

        self.default_order_type = self.config.get("default_order_type", "market")
        self.smart_routing = self.config.get("smart_routing", True)

        #: Shared with the registry rather than re-created, so a connection made
        #: here is visible to every other caller.
        self.broker_registry = broker_registry

        #: Guards concurrent `initialize_brokers` calls. Three call sites race on
        #: a cold container (the trading endpoint, copy-trade, and signal ingest
        #: can all fire before boot warm-up finishes), and without a lock each
        #: would open its own set of broker connections.
        self._brokers_initialized = False
        self._init_lock = asyncio.Lock()

    # -- brokers -------------------------------------------------------------

    async def initialize_brokers(
        self, config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Initialize and connect configured brokers.

        Idempotent and safe to call concurrently. Returns True when at least one
        broker connected.

        Note this returns False rather than raising when nothing connects. A
        missing exchange key is an ordinary configuration state, not an error,
        and callers use this to decide whether the live path is available at all.
        """
        if self._brokers_initialized:
            return True

        async with self._init_lock:
            # Re-check inside the lock: another caller may have finished while
            # this one waited.
            if self._brokers_initialized:
                return True

            try:
                if config is not None:
                    from app.brokers.registry import initialize_brokers

                    initialize_brokers(config)

                results = await self.broker_registry.connect_all()
                successful = [
                    name for name, success in (results or {}).items() if success
                ]
                logger.info(
                    "Execution agent brokers initialized",
                    connected=successful,
                    total=len(results or {}),
                )
                # Marked initialised even with zero brokers: retrying on every
                # order would re-open connections and slow each one down. A
                # broker added later is picked up by `connect_all` on restart.
                self._brokers_initialized = True
                return len(successful) > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("Broker initialization failed", error=str(exc))
                return False

    def brokers_ready(self) -> bool:
        """Whether `initialize_brokers` has run.

        Callers use this to avoid re-initialising; it is not a claim that any
        broker is actually connected, which only the registry knows.
        """
        return self._brokers_initialized

    # -- analysis ------------------------------------------------------------

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate execution conditions (spread, liquidity, slippage).

        Fails safe. Missing or unparseable data yields "not acceptable" rather
        than defaulting to zero and passing: an absent order book previously
        produced `spread_acceptable: True` because `0.0 < 0.5`, so a caller
        checking spread alone would have treated "we know nothing" as "conditions
        are fine".
        """
        blocked = {
            "spread_acceptable": False,
            "liquidity_ok": False,
            "estimated_slippage_bps": 0.0,
        }
        try:
            orderbook = market_data.get("orderbook") or {}
            if not orderbook:
                return blocked

            spread_raw = orderbook.get("spread_pct")
            liquidity_raw = orderbook.get("liquidity_usd")
            # An absent figure is unknown, not zero. Only judge a condition when
            # the value is actually present.
            if spread_raw is None or liquidity_raw is None:
                return blocked

            spread_pct = float(spread_raw)
            liquidity_usd = float(liquidity_raw)

            return {
                "spread_acceptable": 0 <= spread_pct < 0.5,
                "liquidity_ok": liquidity_usd > 10_000,
                "estimated_slippage_bps": round(spread_pct * 100, 2),
            }
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning("Execution analysis input malformed", error=str(exc))
            return {**blocked, "error": "malformed market data"}

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Produce an execution plan.

        The Execution agent does not decide *whether* to trade - that is
        Director / Quant / Risk. It decides whether conditions permit one.
        """
        if not analysis.get("spread_acceptable") or not analysis.get("liquidity_ok"):
            return None

        self.signals_generated += 1
        return {
            "action": "route",
            "symbol": symbol,
            "slippage_bps": analysis.get("estimated_slippage_bps", 0),
            "reasoning": "Execution: conditions acceptable",
        }

    # -- order lifecycle -----------------------------------------------------

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        client_order_id: Optional[str] = None,
    ) -> Trade:
        """Build an unsent `Trade` row.

        This is validation only - no network call and no LLM. An earlier version
        round-tripped every order through the NVIDIA chat API to "validate"
        parameters, which added a multi-second network round trip and a
        single-point-of-failure to the critical path of every order, and could
        raise on a malformed model response. Parameter checking belongs here and
        in the Risk agent, not in a language model.

        Returns a `Trade` with status "pending". It is not attached to a session;
        the caller decides when to persist it.
        """
        clean_symbol = (symbol or "").strip().upper()
        if not clean_symbol:
            raise ValueError("symbol is required to create an order")

        clean_side = (side or "").strip().lower()
        if clean_side not in VALID_SIDES:
            raise ValueError(
                f"invalid side '{side}'; expected one of {VALID_SIDES}"
            )

        clean_type = (order_type or self.default_order_type).strip().lower()
        if clean_type not in VALID_ORDER_TYPES:
            raise ValueError(
                f"invalid order_type '{order_type}'; expected one of "
                f"{VALID_ORDER_TYPES}"
            )

        try:
            clean_quantity = float(quantity)
        except (TypeError, ValueError):
            raise ValueError(f"quantity must be numeric, got {quantity!r}") from None
        if clean_quantity <= 0:
            raise ValueError(f"quantity must be positive, got {clean_quantity}")

        # A limit order without a price would be rejected by the venue; catch it
        # here where the reason can be reported to the caller.
        if clean_type in ("limit", "stop_limit") and limit_price is None:
            raise ValueError(f"{clean_type} order requires limit_price")
        if clean_type in ("stop", "stop_limit") and stop_price is None:
            raise ValueError(f"{clean_type} order requires stop_price")

        return Trade(
            symbol=clean_symbol,
            side=clean_side,
            quantity=clean_quantity,
            price=limit_price,
            order_type=clean_type,
            status="pending",
            agent_name=self.name,
        )

    async def submit_to_broker(
        self,
        trade: Trade,
        broker: str = "auto",
    ) -> Trade:
        """Submit a pending `Trade` to a venue and record the outcome.

        Mutates and returns `trade`; the caller persists it. Never raises on a
        broker failure - the failure is recorded in `trade.status` so the audit
        trail shows what happened instead of the exception escaping and leaving
        the row stuck at "pending" forever.
        """
        if trade is None:
            raise ValueError("submit_to_broker requires a Trade")

        logger.info(
            "Submitting order",
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            broker=broker,
        )

        try:
            results = await self._dispatch(trade, broker)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Transport-level failure: a venue that never answered. Record the
            # reason as well as the status, so an outage is distinguishable from
            # a rejection and from an order that was never attempted.
            logger.error("Broker submission failed", error=str(exc), symbol=trade.symbol)
            trade.status = "error"
            trade.error_detail = f"{type(exc).__name__}: {exc}"
            return trade

        successes = [r for r in results if r.get("success") and r.get("broker")]

        if successes:
            primary = successes[0]
            trade.broker = primary["broker"]
            trade.broker_order_id = primary.get("order_id")
            trade.status = "submitted"
            self.trades_executed += 1

            if len(results) > 1:
                logger.info(
                    "Multi-broker execution",
                    succeeded=len(successes),
                    total=len(results),
                    results=results,
                )
            logger.info(
                "Order submitted",
                broker=trade.broker,
                order_id=trade.broker_order_id,
            )
        else:
            trade.status = "rejected"
            reasons = [
                r.get("error") or r.get("message") or "no reason given"
                for r in results
            ]
            # No venue accepted the order. This is the outcome that matters most
            # to an operator, so it names the actual cause.
            logger.warning(
                "All broker executions failed",
                symbol=trade.symbol,
                reasons=reasons,
            )
            trade.error_detail = "; ".join(str(r) for r in reasons)

        return trade

    async def _dispatch(
        self, trade: Trade, broker: str
    ) -> List[Dict[str, Any]]:
        """Route one order to one or more venues."""
        kwargs: Dict[str, Any] = {"limit_price": trade.price}

        if broker and broker != "auto":
            service = self.broker_registry.get(broker)
            if not service:
                return [{
                    "broker": broker,
                    "success": False,
                    "error": f"broker '{broker}' is not registered",
                }]
            result = await service.submit_order(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                order_type=trade.order_type,
                **kwargs,
            )
            return [{
                "broker": broker,
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
            }]

        if not self.smart_routing:
            asset_class = broker_router.detect_asset_class(trade.symbol)
            service = broker_router.get_primary_broker_for_asset(asset_class)
            if not service:
                return [{
                    "broker": None,
                    "success": False,
                    "error": f"no broker for asset class '{asset_class}'",
                }]
            result = await service.submit_order(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                order_type=trade.order_type,
                **kwargs,
            )
            return [{
                "broker": service.name,
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
            }]

        return await broker_router.execute_with_routing(
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            order_type=trade.order_type,
            **kwargs,
        )

    async def cancel_order(self, trade: Trade) -> bool:
        """Cancel a pending or submitted order at the venue where possible."""
        try:
            if trade.status == "filled":
                logger.warning("Cannot cancel a filled order", trade_id=trade.id)
                return False

            if trade.broker:
                service = self.broker_registry.get(trade.broker)
                if service and getattr(service, "is_connected", False):
                    result = await service.cancel_order(trade.broker_order_id)
                    if result:
                        trade.status = "cancelled"
                        logger.info("Order cancelled", trade_id=trade.id)
                        return True

            # No venue to ask (nothing was submitted yet): the order never left
            # the process, so marking it cancelled is accurate.
            trade.status = "cancelled"
            logger.info("Order cancelled locally", trade_id=trade.id)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Cancel failed", error=str(exc), trade_id=getattr(trade, "id", None))
            return False

    # -- legacy entry point --------------------------------------------------

    async def submit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        venue: str = "auto",
    ) -> Dict[str, Any]:
        """Create and submit an order in one call.

        Thin wrapper over `create_order` + `submit_to_broker`, kept because it is
        the documented single-call entry point.

        It previously imported `place_order` from `app.services.trade_gate`,
        which does not exist, so every call raised ImportError.
        """
        trade = await self.create_order(
            symbol=symbol,
            side=side,
            quantity=amount,
            order_type=order_type,
        )
        await self.initialize_brokers()
        trade = await self.submit_to_broker(trade, broker=venue)
        return {
            "success": trade.status == "submitted",
            "status": trade.status,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "broker": trade.broker,
            "order_id": trade.broker_order_id,
            "error": getattr(trade, "error_detail", None),
        }

    def _get_routing_mode(self) -> str:
        """Current broker routing mode."""
        return broker_router.routing_mode

    # -- lifecycle -----------------------------------------------------------

    async def stop(self):
        """Stop the agent and release broker connections it opened.

        Overrides the base implementation because the base version only flips a
        flag, which would leave sockets open on shutdown. On a free-tier
        container Render sends SIGTERM then force-kills, so an unclosed socket is
        a hung shutdown rather than a clean one.
        """
        await super().stop()
        if not self._brokers_initialized:
            return
        try:
            await asyncio.wait_for(
                self.broker_registry.disconnect_all(), timeout=15.0
            )
            logger.info("Execution agent disconnected brokers")
        except asyncio.TimeoutError:
            logger.warning("Broker disconnect timed out; continuing shutdown")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Broker disconnect failed", error=str(exc))
        finally:
            self._brokers_initialized = False