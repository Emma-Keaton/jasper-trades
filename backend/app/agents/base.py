"""
Base Agent Class
All trading agents inherit from this base class.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import structlog

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Base class for all trading agents.

    Agents are specialized AI-powered modules that each handle one stage
    of the trading pipeline:

    - Director: strategy coordination, market regime, thesis generation
    - Quant: quantitative factor analysis, technical indicators
    - Risk: position sizing, stop-loss, portfolio risk limits
    - Execution: order routing, broker submission, fill tracking
    """

    def __init__(
        self,
        name: str,
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.model = model
        self.config = config or {}
        self.is_active = False

        # Performance tracking
        self.signals_generated = 0
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.win_rate = 0.0

    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market data and return insights."""
        pass

    @abstractmethod
    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a trading signal based on analysis."""
        pass

    async def start(self):
        """Start the agent."""
        self.is_active = True
        logger.info(f"Agent {self.name} started")

    async def stop(self):
        """Stop the agent."""
        self.is_active = False
        logger.info(f"Agent {self.name} stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get agent performance statistics."""
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "is_active": self.is_active,
            "signals_generated": self.signals_generated,
            "trades_executed": self.trades_executed,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate,
        }


class AgentRegistry:
    """Registry for managing multiple agents."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        self._agents[agent.name.lower()] = agent
        logger.info(f"Registered agent: {agent.name}")

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name.lower())

    def get_all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def get_active(self) -> List[BaseAgent]:
        return [a for a in self._agents.values() if a.is_active]

    async def start_all(self) -> Dict[str, bool]:
        """Start every agent, isolating individual failures.

        Returns a name -> started map. One agent failing to start must not leave
        the others inactive, and must not abort the caller's startup sequence.

        This was never called before: agents were registered but never started,
        so `is_active` was False for the whole process lifetime and
        `get_active()` always returned empty - including on the status endpoint
        that reports it to the UI.
        """
        results: Dict[str, bool] = {}
        for agent in list(self._agents.values()):
            try:
                await agent.start()
                results[agent.name] = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Agent failed to start", agent=agent.name, error=str(exc)
                )
                results[agent.name] = False
        return results

    async def stop_all(self, timeout: float = 15.0) -> Dict[str, bool]:
        """Stop every agent, isolating individual failures.

        Each stop is bounded and individually guarded: previously a raise from
        the first agent skipped every remaining one, leaving broker connections
        and background tasks alive through shutdown. Render sends SIGTERM then
        force-kills, so that becomes a hung shutdown rather than a clean one.
        """
        results: Dict[str, bool] = {}
        for agent in list(self._agents.values()):
            try:
                await asyncio.wait_for(agent.stop(), timeout=timeout)
                results[agent.name] = True
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logger.warning(
                    "Agent stop timed out; continuing",
                    agent=agent.name,
                    timeout=timeout,
                )
                results[agent.name] = False
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Agent stop failed; continuing", agent=agent.name, error=str(exc)
                )
                results[agent.name] = False
            finally:
                # Backstop. If an agent's own stop() raised before clearing the
                # flag, `is_active` would stay True for the rest of the process
                # and `get_active()` - which /status reports to the UI - would
                # claim an agent is running after shutdown began. The registry
                # knows the agent is being torn down, so it says so.
                agent.is_active = False
        return results

    def stats(self) -> Dict[str, Any]:
        return {name: agent.get_stats() for name, agent in self._agents.items()}


# Global registry instance
agent_registry = AgentRegistry()
