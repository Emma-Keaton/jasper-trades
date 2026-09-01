"""
Execution Agent
Order routing, broker submission, and fill tracking.
Wraps the existing broker/exchange clients so that the rest of the
agent pipeline never touches raw HTTP or WebSocket details.
"""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
import structlog

logger = structlog.get_logger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Execution Agent - Order routing and broker submission.

    Responsibilities:
    - Translate risk-approved signals into broker orders
    - Route to the correct venue (paper / live / bybit / hyperliquid)
    - Track fill status and report back to the ledger
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Execution",
            model="execution-engine",
            config=config or {},
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate execution conditions (spread, slippage estimate,
        available liquidity).  For now this returns a simple report
        that downstream code can use to decide whether to proceed.
        """
        orderbook = market_data.get("orderbook") or {}
        spread_pct = orderbook.get("spread_pct", 0.0)
        liquidity_usd = orderbook.get("liquidity_usd", 0.0)

        return {
            "spread_acceptable": spread_pct < 0.5,
            "liquidity_ok": liquidity_usd > 10_000,
            "estimated_slippage_bps": round(spread_pct * 100, 2),
        }

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate an execution plan (not a trading signal).

        The Execution agent doesn't decide *whether* to trade —
        that's Director / Quant / Risk.  It decides *how* to execute.
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

    async def submit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        venue: str = "paper",
    ) -> Dict[str, Any]:
        """
        Submit an order to the specified venue.

        This is the main entry-point called by the outer trade gate.
        """
        from app.services.trade_gate import place_order

        result = await place_order(
            symbol=symbol,
            side=side,
            amount=amount,
            order_type=order_type,
            exchange=venue,
        )
        self.trades_executed += 1
        return result
