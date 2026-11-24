"""
Strategy Architect Agent — the free-model brain that proposes, edits and
reconfigures trading strategies so they hit the desired confidence levels.

Uses the LLM provider routed for the "director" task (NVIDIA NIM / Groq /
Gemini per settings) to turn learner stats + backtest history into a new
strategy spec. Proposals are backtest-gated by StrategySuiteService before
they can go active, and scored outcomes feed the learner (self-evolving).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog

from app.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class StrategyArchitectAgent(BaseAgent):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="Architect", model=None, config=config)

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "analysis": "Strategy architect ready — proposes/evolves strategies via the director LLM task.",
            "market_regime": market_data.get("regime", "unknown"),
        }

    async def generate_signal(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Propose (or reconfigure) a strategy for a symbol's conditions."""
        device_id = market_data.get("device_id", "00000000-0000-0000-0000-000000000000")
        from app.database import async_session
        from app.services.strategy_suite import StrategySuiteService

        async with async_session() as db:
            suite = StrategySuiteService(db)
            result = await suite.propose_strategy(
                device_id, target_confidence=float(market_data.get("target_confidence", 70.0))
            )
        self.signals_generated += 1
        return {"agent": self.name, "symbol": symbol, "proposal": result}

    async def start(self):
        await super().start()
        logger.info("Strategy Architect started — will propose/evolve strategies on agent start")
