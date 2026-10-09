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


def _as_float(value: Any, default: float = 0.0) -> float:
    """Parse a numeric field, falling back to `default`.

    Factor output comes from a service and from the database, so a string or
    None must not raise out of signal generation.
    """
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result or result in (float("inf"), float("-inf")):
        return default
    return result


class QuantAgent(BaseAgent):
    """
    Quantitative Analysis Agent.

    Responsibilities:
    - Aggregate factor consensus into a directional signal
    - Surface dominant factor theme and confidence
    - Provide factor-consensus strength for Risk sizing
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Quant",
            model="factor-quant",
            config=config or {},
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run quantitative analysis on the factor consensus output."""
        advise = (market_data.get("advise") or {}) if market_data else {}
        strategy = advise.get("strategy") or {}
        factors = advise.get("factors") or []

        # Build a compact factor breakdown.
        # Entries come from a stored analysis and can be malformed, so each one
        # is probed individually: a single None or stray string previously raised
        # AttributeError and took down signal generation for the whole symbol.
        factor_details = []
        for entry in factors:
            if not isinstance(entry, dict):
                factor_details.append({"name": "unknown", "theme": "unknown"})
                continue
            factor = entry.get("factor")
            if not isinstance(factor, dict):
                factor = {}
            factor_details.append({
                "name": factor.get("name", "unknown"),
                "theme": factor.get("theme", "unknown"),
                "direction": entry.get("direction"),
                "magnitude": entry.get("magnitude"),
                "weight": factor.get("weight", 0),
            })

        direction = advise.get("recommended_direction", "neutral")
        confidence = _as_float(strategy.get("confidence"))

        # `net_signal` is the strength of factor consensus, NOT volatility. It
        # was previously reported as "volatility", which is a different quantity:
        # a strong consensus and a volatile market are unrelated, and downstream
        # Risk sizing treated this label as risk. It is now named for what it
        # measures. Real volatility, when it is available, belongs to the market
        # data path rather than to the factor consensus.
        net = _as_float(strategy.get("net_signal"))
        if abs(net) > 0.5:
            consensus_strength = "strong"
        elif abs(net) > 0.2:
            consensus_strength = "moderate"
        else:
            consensus_strength = "weak"

        return {
            "direction": direction,
            "confidence": confidence,
            "net_signal": net,
            "consensus_strength": consensus_strength,
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
                f"consensus={analysis.get('consensus_strength', 'unknown')}, "
                f"factors={analysis.get('factor_count', 0)}"
            ),
        }
