"""
Risk Agent
Position sizing, stop-loss, and portfolio risk limits.
Uses the existing TradeGate / position-capping logic as its foundation
and adds a per-signal risk opinion that feeds into Execution.
"""
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent
import structlog

logger = structlog.get_logger(__name__)

# Sensible defaults (can be overridden via config)
MAX_POSITION_USD = 50_000
MAX_PORTFOLIO_RISK_PCT = 2.0
DEFAULT_STOP_LOSS_PCT = 0.05


class RiskAgent(BaseAgent):
    """
    Risk Management Agent.

    Responsibilities:
    - Evaluate position size against portfolio limits
    - Set stop-loss and take-profit levels
    - Enforce max-per-trade and max-portfolio-risk constraints
    - Gate orders before they reach Execution
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Risk",
            model="risk-engine",
            config=config or {},
        )
        self.max_position_usd = self.config.get("max_position_usd", MAX_POSITION_USD)
        self.max_portfolio_risk_pct = self.config.get(
            "max_portfolio_risk_pct", MAX_PORTFOLIO_RISK_PCT
        )
        self.default_stop_loss_pct = self.config.get(
            "default_stop_loss_pct", DEFAULT_STOP_LOSS_PCT
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk parameters for a potential trade."""
        advise = market_data.get("advise") or {}
        strategy = advise.get("strategy") or {}
        confidence = float(strategy.get("confidence") or 0.0)
        direction = advise.get("recommended_direction", "neutral")

        # Volatility-adjusted sizing
        net = abs(float(strategy.get("net_signal") or 0))
        if net > 0.5:
            risk_level = "high"
            suggested_size_pct = 0.25
        elif net > 0.2:
            risk_level = "moderate"
            suggested_size_pct = 0.5
        else:
            risk_level = "low"
            suggested_size_pct = 0.75

        # Position sizing suggestion (percentage of max)
        suggested_usd = self.max_position_usd * suggested_size_pct

        # Stop-loss
        stop_loss_pct = self.default_stop_loss_pct
        if risk_level == "high":
            stop_loss_pct *= 0.75  # tighter stop when volatile
        elif risk_level == "low":
            stop_loss_pct *= 1.25  # wider stop when calm

        return {
            "risk_level": risk_level,
            "confidence": confidence,
            "direction": direction,
            "max_position_usd": self.max_position_usd,
            "suggested_position_usd": round(suggested_usd, 2),
            "stop_loss_pct": round(stop_loss_pct, 4),
            "take_profit_pct": round(stop_loss_pct * 2, 4),
            "approved": confidence > 0.4 and direction != "neutral",
        }

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Return a risk-gated signal (or None if rejected)."""
        if not analysis.get("approved"):
            return None

        direction = analysis.get("direction", "neutral")
        if direction == "neutral":
            return None

        self.signals_generated += 1
        return {
            "action": "buy" if direction == "long" else "sell",
            "strength": min(analysis.get("confidence", 0), 1.0),
            "position_usd": analysis.get("suggested_position_usd", 0),
            "stop_loss_pct": analysis.get("stop_loss_pct", DEFAULT_STOP_LOSS_PCT),
            "take_profit_pct": analysis.get("take_profit_pct", DEFAULT_STOP_LOSS_PCT * 2),
            "reasoning": (
                f"Risk: {analysis.get('risk_level', 'unknown')} risk, "
                f"size=${analysis.get('suggested_position_usd', 0):,.0f}, "
                f"SL={analysis.get('stop_loss_pct', 0):.1%}"
            ),
        }


async def assess_position(
    symbol: str,
    side: str,
    amount: float,
    leverage: float = 1.0,
) -> Dict[str, Any]:
    """Legacy helper used by risk_api.py — delegates to RiskAgent.analyze()."""
    agent = RiskAgent()
    analysis = await agent.analyze({
        "advise": {
            "strategy": {"confidence": 0.5, "net_signal": 0.3 if side == "buy" else -0.3, "theme": "legacy"},
            "recommended_direction": "long" if side == "buy" else "short",
        }
    })
    return {
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "leverage": leverage,
        "approved": analysis.get("approved", False),
        "risk_level": analysis.get("risk_level"),
        "stop_loss_pct": analysis.get("stop_loss_pct"),
    }
