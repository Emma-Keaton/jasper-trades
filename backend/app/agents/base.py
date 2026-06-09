"""
Base Agent Class
All trading agents inherit from this base class.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog
from app.nvidia_nim import nvidia_client
from app.models import Signal

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Base class for all trading agents.
    
    Agents are AI-powered decision makers that can:
    - Analyze market data
    - Generate trading signals
    - Execute trades (through execution agent)
    - Manage risk
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
        self.nvidia_client = nvidia_client
        
        # Performance tracking
        self.signals_generated = 0
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.win_rate = 0.0
        
        # Internal state
        self._current_signals: List[Signal] = []
    
    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and return insights.
        
        Args:
            market_data: Dictionary containing price, volume, indicators, etc.
        
        Returns:
            Analysis results
        """
        pass
    
    @abstractmethod
    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on analysis.
        
        Args:
            symbol: Trading symbol (e.g., AAPL, BTC/USD)
            analysis: Results from analyze()
        
        Returns:
            Signal object or None if no signal
        """
        pass
    
    async def execute(self, signal: Signal) -> bool:
        """
        Execute a trade based on signal.
        Default implementation delegates to ExecutionAgent.
        
        Args:
            signal: Signal to execute
        
        Returns:
            True if execution successful
        """
        logger.info(f"Agent {self.name} executing signal for {signal.symbol}")
        # This would typically call the ExecutionAgent
        return True
    
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
        """Register an agent."""
        self._agents[agent.name.lower()] = agent
        logger.info(f"Registered agent: {agent.name}")
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name.lower())
    
    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def get_active(self) -> List[BaseAgent]:
        """Get all active agents."""
        return [a for a in self._agents.values() if a.is_active]
    
    async def start_all(self):
        """Start all agents."""
        for agent in self._agents.values():
            await agent.start()
    
    async def stop_all(self):
        """Stop all agents."""
        for agent in self._agents.values():
            await agent.stop()
    
    def stats(self) -> Dict[str, Any]:
        """Get stats for all agents."""
        return {name: agent.get_stats() for name, agent in self._agents.items()}


# Global registry instance
agent_registry = AgentRegistry()
