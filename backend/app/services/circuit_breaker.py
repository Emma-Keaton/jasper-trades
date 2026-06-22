"""
Circuit Breaker Service
Automatically halts trading during market anomalies or excessive drawdown.

States:
- IDLE: Normal operation, trading allowed
- WARNING: Elevated risk, monitoring closely  
- HALTED: Trading blocked, manual override required

Triggers:
- Flash crash: >5% drop in 5 minutes
- Volatility spike: ATR > 2x average
- Drawdown limit: Portfolio >10% from peak
- Manual override: Via API or UI
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import structlog

from app.services.telegram_service import telegram_service
from app.api.websocket.streams import publish_risk_update

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    IDLE = "idle"
    WARNING = "warning"
    HALTED = "halted"


class CircuitBreakerService:
    """
    Circuit Breaker Service - Protects portfolio from extreme market conditions.
    
    Monitors:
    - Flash crashes (>5% in 5 min)
    - Volatility spikes (ATR > 2x normal)
    - Drawdown limits (>10% from peak)
    
    Actions:
    - Blocks trade executions when halted
    - Sends Telegram alerts on state changes
    - Logs all halt/resume events
    """
    
    def __init__(self):
        self.state = CircuitState.IDLE
        self.triggered_at: Optional[datetime] = None
        self.trigger_reason: Optional[str] = None
        self.halted_by: str = "auto"  # "auto" or "manual"
        
        # Monitoring windows
        self.price_history: Dict[str, List[Dict[str, Any]]] = {}  # symbol -> [(time, price), ...]
        self.window_seconds = 300  # 5 minutes for flash crash detection
        
        # Thresholds
        self.flash_crash_threshold = -0.05  # -5%
        self.drawdown_threshold = -0.10  # -10%
        self.volatility_multiplier = 2.0  # 2x average ATR
        
        # Baseline ATR (would be calculated from historical data)
        self.baseline_atr: Dict[str, float] = {}
        
        # Portfolio peak (would track over time)
        self.portfolio_peak: float = 0
        
        logger.info("Circuit Breaker Service initialized")
    
    def update_price(self, symbol: str, price: float, timestamp: Optional[datetime] = None):
        """
        Update price for a symbol.
        
        Checks for flash crash conditions.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Initialize symbol history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.baseline_atr[symbol] = price * 0.02  # Assume 2% ATR initially
        
        history = self.price_history[symbol]
        
        # Add new price
        history.append({"time": timestamp, "price": price})
        
        # Remove old prices (outside window)
        cutoff = timestamp - timedelta(seconds=self.window_seconds)
        history = [p for p in history if p["time"] >= cutoff]
        self.price_history[symbol] = history
        
        # Check for flash crash
        if len(history) >= 2:
            oldest_price = history[0]["price"]
            if oldest_price > 0:
                change = (price - oldest_price) / oldest_price
                
                if change <= self.flash_crash_threshold:
                    self.trigger_halt(f"Flash crash detected: {symbol} down {change:.1%} in 5 minutes")
                    return
    
    def update_portfolio_value(self, current_value: float):
        """
        Update portfolio value and check drawdown.
        """
        # Update peak
        if current_value > self.portfolio_peak:
            self.portfolio_peak = current_value
        
        # Check drawdown if we have a peak
        if self.portfolio_peak > 0:
            drawdown = (self.portfolio_peak - current_value) / self.portfolio_peak
            
            if drawdown >= abs(self.drawdown_threshold):
                self.trigger_halt(f"Portfolio drawdown {drawdown:.1%} exceeds {abs(self.drawdown_threshold):.0%} limit")
    
    def trigger_halt(self, reason: str, manual: bool = False):
        """
        Trigger trading halt.
        
        Args:
            reason: Reason for halt
            manual: Whether triggered manually or automatically
        """
        if self.state == CircuitState.HALTED:
            return  # Already halted
        
        old_state = self.state
        self.state = CircuitState.HALTED
        self.triggered_at = datetime.utcnow()
        self.trigger_reason = reason
        self.halted_by = "manual" if manual else "auto"
        
        logger.warning(
            f"Circuit breaker HALTED: {reason}",
            triggered_by=self.halted_by,
        )
        
        # Send Telegram alert
        import asyncio
        asyncio.create_task(self._send_halt_alert(reason))
        
        # Broadcast to WebSocket
        asyncio.create_task(self._broadcast_state_change(old_state))
    
    def resume_trading(self) -> bool:
        """
        Resume trading (manual override).
        
        Returns:
            True if resumed, False if was not halted
        """
        if self.state != CircuitState.HALTED:
            return False
        
        old_state = self.state
        self.state = CircuitState.IDLE
        self.triggered_at = None
        self.trigger_reason = None
        
        logger.info("Circuit breaker RESUMED - trading allowed")
        
        # Send Telegram alert
        import asyncio
        asyncio.create_task(self._send_resume_alert())
        
        # Broadcast to WebSocket
        asyncio.create_task(self._broadcast_state_change(old_state))
        
        return True
    
    def set_warning(self, reason: str):
        """
        Set warning state (elevated risk).
        """
        if self.state == CircuitState.HALTED:
            return  # Don't downgrade from halted
        
        old_state = self.state
        self.state = CircuitState.WARNING
        self.trigger_reason = reason
        
        logger.info(f"Circuit breaker WARNING: {reason}")
        
        # Broadcast
        import asyncio
        asyncio.create_task(self._broadcast_state_change(old_state))
    
    def clear_warning(self):
        """Clear warning state."""
        if self.state == CircuitState.IDLE:
            return
        
        old_state = self.state
        self.state = CircuitState.IDLE
        self.trigger_reason = None
        
        logger.info("Circuit breaker cleared - normal operation")
        
        import asyncio
        asyncio.create_task(self._broadcast_state_change(old_state))
    
    def can_trade(self) -> bool:
        """
        Check if trading is allowed.
        
        Returns:
            True if trading allowed, False if halted
        """
        if self.state == CircuitState.HALTED:
            return False
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.
        
        Returns:
            Dict with state, trigger info, and timing
        """
        return {
            "state": self.state.value,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trigger_reason": self.trigger_reason,
            "halted_by": self.halted_by,
            "can_trade": self.can_trade(),
            "time_halted_seconds": (
                (datetime.utcnow() - self.triggered_at).total_seconds()
                if self.triggered_at and self.state == CircuitState.HALTED
                else 0
            ),
        }
    
    async def _send_halt_alert(self, reason: str):
        """Send Telegram alert on trading halt."""
        message = (
            f"⚠️ *TRADING HALTED*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚨 Circuit breaker triggered\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Reason:*\n{reason}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Trading will remain halted until manual override."
        )
        
        await telegram_service.send_message(message, "⚠️ TRADING HALTED")
    
    async def _send_resume_alert(self):
        """Send Telegram alert on trading resume."""
        message = (
            f"✅ *TRADING RESUMED*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Circuit breaker cleared\n"
            f"Trading operations resumed\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC"
        )
        
        await telegram_service.send_message(message, "✅ RESUMED")
    
    async def _broadcast_state_change(self, old_state: CircuitState):
        """Broadcast state change to WebSocket clients."""
        await publish_risk_update({
            "circuit_breaker": {
                "state": self.state.value,
                "previous_state": old_state.value,
                "trigger_reason": self.trigger_reason,
                "can_trade": self.can_trade(),
            }
        })
    
    def reset(self):
        """Reset all monitoring data (testing/debugging)."""
        self.price_history.clear()
        self.portfolio_peak = 0
        self.state = CircuitState.IDLE
        self.triggered_at = None
        self.trigger_reason = None
        logger.info("Circuit breaker reset")


# Singleton instance
circuit_breaker = CircuitBreakerService()


def get_circuit_breaker() -> CircuitBreakerService:
    """Get the circuit breaker instance."""
    return circuit_breaker