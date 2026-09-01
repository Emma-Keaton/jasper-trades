"""
Director Agent
Coordinates the trading pipeline: market regime, strategy theses,
and inter-agent orchestration.  Uses the factor consensus service
as its analytical backbone (no external LLM dependency required).
"""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
import structlog

logger = structlog.get_logger(__name__)


class DirectorAgent(BaseAgent):
    """
    Director Agent - Strategy coordination and market regime.

    This agent:
    - Determines the overall market regime (bullish / bearish / sideways)
    - Generates high-level trading theses
    - Coordinates Quant, Risk, and Execution agents
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Director",
            model="factor-consensus",
            config=config or {},
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market regime from the factor consensus output.

        market_data is expected to contain:
        - ``advise``: the dict returned by AlphaFactorService.advise_for_trade()
        - ``ohlcv``: recent candles for context
        """
        advise = market_data.get("advise") or {}
        strategy = advise.get("strategy") or {}
        direction = advise.get("recommended_direction", "neutral")
        confidence = float(strategy.get("confidence") or 0.0)
        theme = strategy.get("theme", "mixed")

        if direction == "long":
            regime = "bullish"
        elif direction == "short":
            regime = "bearish"
        else:
            regime = "sideways"

        return {
            "regime": regime,
            "direction": direction,
            "theme": theme,
            "confidence": confidence,
            "net_signal": strategy.get("net_signal"),
            "recommendation": direction if confidence > 0.6 else "hold",
        }

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a strategic signal from analysis."""
        direction = analysis.get("direction", "neutral")
        confidence = analysis.get("confidence", 0)

        if direction == "neutral" or confidence < 0.5:
            return None

        self.signals_generated += 1
        return {
            "action": "buy" if direction == "long" else "sell",
            "strength": min(confidence, 1.0),
            "reasoning": f"Director: {analysis.get('theme', 'mixed')} theme, {analysis.get('regime', 'unknown')} regime",
        }
