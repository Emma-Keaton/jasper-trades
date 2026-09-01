"""
Quant Agent
Provides quantitative analysis: technical indicators, factor scores,
and statistical signals.  Works from the factor advisor's alpha-zoo
output — no external LLM required.
"""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
import structlog

logger = structlog.get_logger(__name__)


class QuantAgent(BaseAgent):
    """
    Quantitative Analysis Agent.

    Responsibilities:
    - Aggregate factor consensus into a directional signal
    - Surface dominant factor theme and confidence
    - Provide volatility / regime context for Risk sizing
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Quant",
            model="factor-quant",
            config=config or {},
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run quantitative analysis on the factor consensus output."""
        advise = market_data.get("advise") or {}
        strategy = advise.get("strategy") or {}
        factors = advise.get("factors") or []

        # Build a compact factor breakdown
        factor_details = []
        for f in factors:
            factor_details.append({
                "name": f.get("factor", {}).get("name", "unknown"),
                "theme": f.get("factor", {}).get("theme", "unknown"),
                "direction": f.get("direction"),
                "magnitude": f.get("magnitude"),
                "weight": f.get("factor", {}).get("weight", 0),
            })

        direction = advise.get("recommended_direction", "neutral")
        confidence = float(strategy.get("confidence") or 0.0)

        # Estimate volatility category from net_signal magnitude
        net = float(strategy.get("net_signal") or 0)
        abs_net = abs(net)
        if abs_net > 0.5:
            volatility = "high"
        elif abs_net > 0.2:
            volatility = "moderate"
        else:
            volatility = "low"

        return {
            "direction": direction,
            "confidence": confidence,
            "net_signal": net,
            "volatility": volatility,
            "dominant_theme": strategy.get("theme", "mixed"),
            "factors": factor_details,
            "factor_count": len(factors),
        }

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a quant signal from factor analysis."""
        direction = analysis.get("direction", "neutral")
        confidence = analysis.get("confidence", 0)

        if direction == "neutral" or confidence < 0.4:
            return None

        self.signals_generated += 1
        return {
            "action": "buy" if direction == "long" else "sell",
            "strength": min(confidence, 1.0),
            "reasoning": (
                f"Quant: {analysis.get('dominant_theme', 'mixed')} dominant, "
                f"vol={analysis.get('volatility', 'unknown')}, "
                f"factors={analysis.get('factor_count', 0)}"
            ),
        }
