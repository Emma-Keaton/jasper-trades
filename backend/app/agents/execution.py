"""
Execution Agent
Generates and executes orders.
From AutoHedge + AI-Trader.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.agents.base import BaseAgent
from app.nvidia_nim import nvidia_client
from app.models import Signal, Trade
from app.brokers import (
    get_broker,
    get_broker_for_asset,
    broker_registry,
)
from app.brokers.router import broker_router
from app.services.agent_reach.market_intel_service import get_market_intel_service
import structlog

logger = structlog.get_logger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Execution Agent - Order generation and execution.

    This agent:
    - Converts signals to orders
    - Optimizes execution
    - Manages order lifecycle
    - Tracks execution quality
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Execution",
            model="meta/llama-3.2-3b-instruct",  # Fast model for execution
            config=config or {},
        )

        # Execution parameters
        self.default_order_type = self.config.get('default_order_type', 'market')
        self.smart_routing = self.config.get('smart_routing', True)

        # Broker registry reference
        self.broker_registry = broker_registry
        self._brokers_initialized = False

    async def initialize_brokers(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize all configured brokers.

        Returns:
            True if at least one broker initialized successfully
        """
        if self._brokers_initialized:
            return True

        try:
            from app.brokers.registry import initialize_brokers
            initialize_brokers(config)
            
            # Connect all brokers
            results = await self.broker_registry.connect_all()
            
            successful = [name for name, success in results.items() if success]
            logger.info("Brokers initialized", brokers=successful)
            
            self._brokers_initialized = True
            return len(successful) > 0
            
        except Exception as e:
            logger.error(f"Failed to initialize brokers: {e}")
            return False

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze execution conditions with market intelligence.

        Returns:
            Execution quality metrics and news context
        """
        try:
            spread = market_data.get('spread', 0)
            volume = market_data.get('volume', 0)
            volatility = market_data.get('volatility', 0)
            symbol = market_data.get('symbol', '')

            # Execution quality assessment
            liquidity_score = min(1.0, volume / 1000000) if volume else 0.5
            spread_score = max(0, 1 - spread * 100)  # Lower spread = better

            # Get market intelligence for execution timing
            news_context = {}
            if symbol:
                try:
                    market_intel_service = get_market_intel_service()
                    sentiment = await market_intel_service.get_sentiment(ticker=symbol)
                    if sentiment and sentiment.get('recent_articles', 0) > 0:
                        news_context = {
                            'recent_news_count': sentiment.get('recent_articles', 0),
                            'sentiment_score': sentiment.get('overall_score', 50),
                            'news_driven_volatility': sentiment.get('overall_score', 50) > 70 or sentiment.get('overall_score', 50) < 30
                        }
                except Exception as intel_error:
                    logger.warning(f"Market intel lookup failed for {symbol}: {intel_error}")

            return {
                'liquidity_score': liquidity_score,
                'spread_score': spread_score,
                'volatility': volatility,
                'execution_quality': (liquidity_score + spread_score) / 2,
                'news_context': news_context,
            }

        except Exception as e:
            logger.error(f"Execution analysis error: {e}")
            return {"error": str(e)}

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Execution agent doesn't typically generate signals.
        """
        return None

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
        """
        Create a trade order.

        Args:
            symbol: Trading symbol
            side: buy/sell
            quantity: Number of shares/contracts
            order_type: market/limit/stop/stop_limit
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: day/gtc/ioc
            client_order_id: Optional client order ID

        Returns:
            Trade object
        """
        try:
            # Use NVIDIA NIM to validate order parameters
            prompt = f"""
Validate and optimize this order:

Symbol: {symbol}
Side: {side}
Quantity: {quantity}
Order Type: {order_type}
Limit Price: {limit_price}
Stop Price: {stop_price}
Time in Force: {time_in_force}

Output JSON with:
- validated: true/false
- optimized_params: dict
- warnings: list
- execution_strategy: "immediate" or "patient"
"""

            messages = [
                {"role": "system", "content": "You are an execution optimization AI."},
                {"role": "user", "content": prompt}
            ]

            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='execution',
            )

            import json
            try:
                validation = json.loads(response)
                logger.info(f"Order validation: {validation}")
            except:
                validation = {}

            # Create Trade object
            trade = Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=limit_price,
                order_type=order_type,
                status="pending",
                agent_name=self.name,
                created_at=datetime.utcnow(),
            )

            return trade

        except Exception as e:
            logger.error(f"Order creation error: {e}")
            raise

    async def submit_to_broker(
        self,
        trade: Trade,
        broker: str = "auto",
    ) -> Trade:
        """
        Submit trade to broker for execution using broker router.

        Args:
            trade: Trade to submit
            broker: Broker name (binance, solana) or "auto" for routing

        Returns:
            Updated Trade with broker_order_id
        """
        try:
            logger.info(f"Submitting {trade.side} {trade.quantity} {trade.symbol}")

            # Use broker router for intelligent routing
            if broker == "auto":
                # Execute with routing based on current routing mode
                results = await broker_router.execute_with_routing(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    order_type=trade.order_type,
                    limit_price=trade.price,
                )
            else:
                # Submit to specific broker
                broker_service = self.broker_registry.get(broker)
                if not broker_service:
                    logger.error(f"Broker {broker} not available")
                    trade.status = "rejected"
                    return trade
                
                result = await broker_service.submit_order(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    order_type=trade.order_type,
                    limit_price=trade.price,
                )
                results = [{
                    "broker": broker,
                    "success": result.success,
                    "order_id": result.order_id,
                    "message": result.message,
                }]

            # Update trade with results
            successful_executions = [r for r in results if r.get("success")]
            
            if successful_executions:
                # At least one execution succeeded
                primary = successful_executions[0]
                trade.broker = primary["broker"]
                trade.broker_order_id = primary["order_id"]
                trade.status = "submitted"
                
                # Log all executions
                if len(results) > 1:
                    logger.info(
                        f"Multi-broker execution: {len(successful_executions)}/{len(results)} succeeded",
                        executions=results,
                    )
                else:
                    logger.info(
                        f"Order submitted successfully",
                        broker=trade.broker,
                        order_id=trade.broker_order_id,
                    )
            else:
                # All executions failed
                trade.status = "rejected"
                error_messages = [r.get("error") or r.get("message") for r in results]
                logger.warning(f"All broker executions failed: {error_messages}")

            return trade

        except Exception as e:
            logger.error(f"Broker submission error: {e}")
            trade.status = "error"
            return trade

    def _get_routing_mode(self) -> str:
        """Get current routing mode from broker router."""
        return broker_router.routing_mode

    async def cancel_order(self, trade: Trade) -> bool:
        """Cancel an order."""
        try:
            if trade.status == "filled":
                logger.warning(f"Cannot cancel filled order: {trade.id}")
                return False

            # Get broker service
            if trade.broker:
                broker_service = self.broker_registry.get(trade.broker)
                if broker_service and broker_service.is_connected:
                    result = await broker_service.cancel_order(trade.broker_order_id)
                    if result:
                        trade.status = "cancelled"
                        logger.info(f"Cancelled order {trade.id} via {trade.broker}")
                        return True

            # Fallback: just mark as cancelled
            trade.status = "cancelled"
            logger.info(f"Cancelled order {trade.id}")
            return True

        except Exception as e:
            logger.error(f"Cancel error: {e}")
            return False

    def get_execution_quality(self, trade: Trade) -> Dict[str, Any]:
        """
        Evaluate execution quality.

        Returns:
            Execution quality metrics
        """
        return {
            'trade_id': trade.id,
            'symbol': trade.symbol,
            'side': trade.side,
            'status': trade.status,
            'broker': trade.broker,
        }