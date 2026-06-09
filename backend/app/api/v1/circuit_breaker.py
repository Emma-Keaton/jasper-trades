"""
Circuit Breaker API
Control and monitor the trading circuit breaker
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import structlog

from app.services.circuit_breaker import get_circuit_breaker, CircuitBreakerService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/circuit-breaker", tags=["circuit-breaker"])


class HaltRequest(BaseModel):
    reason: str = "Manual halt via API"


@router.get("/status")
async def get_circuit_breaker_status():
    """
    Get current circuit breaker status.
    
    Returns:
    - state: "idle", "warning", or "halted"
    - trigger_reason: Why it was triggered
    - triggered_at: Timestamp of trigger
    - can_trade: Whether trading is allowed
    """
    cb = get_circuit_breaker()
    return cb.get_status()


@router.post("/halt")
async def trigger_halt(request: Optional[HaltRequest] = None):
    """
    Manually trigger trading halt.
    
    Use this to stop trading during:
    - Market emergencies
    - System maintenance
    - Risk concerns
    """
    cb = get_circuit_breaker()
    
    reason = request.reason if request else "Manual halt via API"
    cb.trigger_halt(reason, manual=True)
    
    return {
        "success": True,
        "message": "Trading halted",
        "reason": reason,
        "state": "halted",
    }


@router.post("/resume")
async def resume_trading():
    """
    Resume trading after halt.
    
    Requires manual confirmation - this overrides the circuit breaker.
    """
    cb = get_circuit_breaker()
    
    if cb.state.value != "halted":
        raise HTTPException(status_code=400, detail="Circuit breaker is not halted")
    
    cb.resume_trading()
    
    return {
        "success": True,
        "message": "Trading resumed",
        "state": "idle",
    }


@router.post("/warning")
async def set_warning(reason: str):
    """
    Set warning state (elevated risk monitoring).
    
    Trading is still allowed, but system is on high alert.
    """
    cb = get_circuit_breaker()
    cb.set_warning(reason)
    
    return {
        "success": True,
        "message": "Warning state set",
        "state": "warning",
        "reason": reason,
    }


@router.post("/clear")
async def clear_warning():
    """Clear warning state and return to normal operation."""
    cb = get_circuit_breaker()
    cb.clear_warning()
    
    return {
        "success": True,
        "message": "Warning cleared",
        "state": "idle",
    }


@router.post("/reset")
async def reset_circuit_breaker():
    """
    Reset all circuit breaker data.
    
    Use for testing/debugging only. Clears monitoring history.
    """
    cb = get_circuit_breaker()
    cb.reset()
    
    return {
        "success": True,
        "message": "Circuit breaker reset",
        "state": "idle",
    }


@router.get("/config")
async def get_config():
    """Get circuit breaker configuration thresholds."""
    cb = get_circuit_breaker()
    
    return {
        "flash_crash_threshold": cb.flash_crash_threshold * 100,  # As percentage
        "drawdown_threshold": cb.drawdown_threshold * 100,
        "volatility_multiplier": cb.volatility_multiplier,
        "window_seconds": cb.window_seconds,
    }


@router.post("/check-trade")
async def check_trade_allowed():
    """
    Check if a trade would be allowed right now.
    
    Call this before submitting a trade to verify circuit breaker status.
    """
    cb = get_circuit_breaker()
    can_trade = cb.can_trade()
    
    if not can_trade:
        return {
            "allowed": False,
            "reason": f"Trading halted: {cb.trigger_reason}",
            "state": cb.state.value,
        }
    
    return {
        "allowed": True,
        "state": cb.state.value,
    }