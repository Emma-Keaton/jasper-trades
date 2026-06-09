"""
QuantDinger Agent Gateway - Scoped API tokens for AI agents.

Features:
- Issue scoped tokens (paper-only by default)
- Audit logging (append-only trail)
- Rate limiting + symbol allowlists
- Mandate-based trading (max size, leverage, daily cap)
- Instant kill switch

Safety model:
- Paper-only by default
- Live trading requires explicit server unlock + user mandate
- Every agent call is audit-logged
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func
import hashlib
import secrets
import structlog

from app.database import async_session
from app.models import Agent

logger = structlog.get_logger(__name__)


class AgentGateway:
    """
    QuantDinger-style Agent Gateway for safe AI trading.
    
    Allows external AI agents (Cursor, Claude Code, etc.) to trade
    with scoped permissions and full audit trail.
    """
    
    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}  # In-memory token store
        self.audit_log: List[Dict[str, Any]] = []  # In-memory audit log
    
    def generate_token(self, agent_name: str, scopes: List[str]) -> str:
        """
        Generate a scoped agent token.
        
        Args:
            agent_name: Name of the agent
            scopes: List of permissions (e.g., ["read", "trade_paper", "backtest"])
        
        Returns:
            API token string
        """
        # Generate random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Store token metadata
        self.tokens[token_hash] = {
            "agent_name": agent_name,
            "scopes": scopes,
            "paper_only": True,  # SAFE DEFAULT
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "rate_limit": 100,  # calls per hour
            "symbol_allowlist": None,  # None = all symbols allowed
            "max_order_size": 1000,  # max shares per order
            "max_daily_notional": 10000,  # max $ per day
            "daily_notional_used": 0.0,
            "is_active": True
        }
        
        logger.info(f"Generated token for {agent_name} with scopes: {scopes}")
        return f"qd_agent_{raw_token}"
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate an agent token and return its metadata.
        
        Args:
            token: Full token string (e.g., "qd_agent_xxxxx")
        
        Returns:
            Token metadata if valid, None if invalid
        """
        if not token.startswith("qd_agent_"):
            return None
        
        raw_token = token.replace("qd_agent_", "")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        token_data = self.tokens.get(token_hash)
        if not token_data:
            logger.warning(f"Invalid token attempt")
            return None
        
        # Check expiration
        if datetime.utcnow() > token_data["expires_at"]:
            logger.warning(f"Token expired for {token_data['agent_name']}")
            return None
        
        # Check if active
        if not token_data["is_active"]:
            logger.warning(f"Token deactivated for {token_data['agent_name']}")
            return None
        
        return token_data
    
    def check_scope(self, token: str, required_scope: str) -> bool:
        """Check if token has required scope."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        return required_scope in token_data["scopes"]
    
    def can_trade_live(self, token: str) -> bool:
        """Check if token allows live trading (default: NO)."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        # PAPER-ONLY BY DEFAULT - explicit override required
        return not token_data["paper_only"]
    
    def log_audit(
        self,
        token: str,
        action: str,
        details: Dict[str, Any],
        result: str = "success"
    ):
        """
        Log an agent action to the audit trail.
        
        Args:
            token: Agent token
            action: Action performed (e.g., "place_order", "get_positions")
            details: Action details
            result: success/failure/blocked
        """
        token_data = self.validate_token(token)
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": token_data["agent_name"] if token_data else "unknown",
            "action": action,
            "details": details,
            "result": result
        }
        
        self.audit_log.append(entry)
        
        # Log to structured logger
        logger.info(
            f"Audit: {action}",
            agent=entry["agent_name"],
            result=result,
            details=details
        )
    
    def check_rate_limit(self, token: str) -> bool:
        """Check if agent is within rate limit."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        # Count recent calls (last hour)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_calls = sum(
            1 for entry in self.audit_log
            if entry["agent_name"] == token_data["agent_name"]
            and datetime.fromisoformat(entry["timestamp"]) > hour_ago
        )
        
        return recent_calls < token_data["rate_limit"]
    
    def check_symbol_allowed(self, token: str, symbol: str) -> bool:
        """Check if symbol is in allowlist."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        allowlist = token_data["symbol_allowlist"]
        if allowlist is None:
            return True  # No restrictions
        
        return symbol.upper() in [s.upper() for s in allowlist]
    
    def check_order_size(self, token: str, quantity: float) -> bool:
        """Check if order size is within limits."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        return quantity <= token_data["max_order_size"]
    
    def check_daily_notional(
        self,
        token: str,
        symbol: str,
        price: float,
        quantity: float
    ) -> bool:
        """Check if order is within daily notional limit."""
        token_data = self.validate_token(token)
        if not token_data:
            return False
        
        order_notional = price * quantity
        remaining = token_data["max_daily_notional"] - token_data["daily_notional_used"]
        
        return order_notional <= remaining
    
    def record_order(self, token: str, symbol: str, price: float, quantity: float):
        """Record order against daily notional limit."""
        token_data = self.validate_token(token)
        if not token_data:
            return
        
        order_notional = price * quantity
        token_data["daily_notional_used"] += order_notional
    
    def reset_daily_limits(self):
        """Reset daily notional usage (call at start of each trading day)."""
        for token_data in self.tokens.values():
            token_data["daily_notional_used"] = 0.0
        
        logger.info("Reset daily notional limits for all agents")
    
    def deactivate_token(self, token: str) -> bool:
        """Immediately deactivate a token (kill switch)."""
        token_hash = hashlib.sha256(
            token.replace("qd_agent_", "").encode()
        ).hexdigest()
        
        if token_hash in self.tokens:
            self.tokens[token_hash]["is_active"] = False
            self.log_audit(token, "deactivate_token", {}, "success")
            logger.warning(f"Token {token} deactivated")
            return True
        
        return False
    
    def get_audit_log(
        self,
        agent_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        if agent_name:
            filtered = [
                entry for entry in self.audit_log
                if entry["agent_name"] == agent_name
            ]
            return filtered[-limit:]
        
        return self.audit_log[-limit:]
    
    def get_token_stats(self, token: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for a token."""
        token_data = self.validate_token(token)
        if not token_data:
            return None
        
        # Count actions by type
        action_counts = {}
        for entry in self.audit_log:
            if entry["agent_name"] == token_data["agent_name"]:
                action = entry["action"]
                action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "agent_name": token_data["agent_name"],
            "scopes": token_data["scopes"],
            "paper_only": token_data["paper_only"],
            "rate_limit": token_data["rate_limit"],
            "symbol_allowlist": token_data["symbol_allowlist"],
            "max_order_size": token_data["max_order_size"],
            "max_daily_notional": token_data["max_daily_notional"],
            "daily_notional_used": token_data["daily_notional_used"],
            "action_counts": action_counts,
            "created_at": token_data["created_at"].isoformat(),
            "expires_at": token_data["expires_at"].isoformat()
        }


# Global instance
agent_gateway = AgentGateway()