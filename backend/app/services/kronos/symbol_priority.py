"""
Symbol Priority Queue for 4GB RAM Systems

Tiered prediction scheduling to minimize RAM usage:
- Tier 1: Holdings (every 5 min)
- Tier 2: Watchlist (every 30 min)
- Tier 3: Candidates (every 4 hours)
- Tier 4: Market scan (once daily)
"""
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SymbolTier(Enum):
    """Symbol priority tiers for scheduling."""
    TIER_1 = "holdings"        # Every 5 min - your actual holdings
    TIER_2 = "watchlist"       # Every 30 min - symbols you're watching
    TIER_3 = "candidates"      # Every 4 hours - Top-K candidates
    TIER_4 = "market_scan"     # Once daily - broad market scan


class SymbolPriorityQueue:
    """
    Manage symbol prediction priorities for 4GB RAM systems.
    
    Instead of predicting 100 symbols every 5 minutes (which would
    overwhelm 4GB RAM), we use a tiered approach:
    
    - Tier 1: 5 symbols → every 5 min  → 60 predictions/hour
    - Tier 2: 10 symbols → every 30 min → 20 predictions/hour
    - Tier 3: 20 symbols → every 4 hours → 5 predictions/hour
    - Tier 4: 100 symbols → once daily → 4 predictions/hour
    
    Total: ~89 predictions/hour average (manageable on 4GB RAM)
    """
    
    def __init__(self):
        self._symbols: Dict[SymbolTier, Set[str]] = {
            SymbolTier.TIER_1: set(),
            SymbolTier.TIER_2: set(),
            SymbolTier.TIER_3: set(),
            SymbolTier.TIER_4: set(),
        }
        
        self._last_prediction: Dict[str, datetime] = {}
        self._tier_intervals: Dict[SymbolTier, timedelta] = {
            SymbolTier.TIER_1: timedelta(minutes=5),
            SymbolTier.TIER_2: timedelta(minutes=30),
            SymbolTier.TIER_3: timedelta(hours=4),
            SymbolTier.TIER_4: timedelta(days=1),
        }
        
        self._ohlcv_data: Dict[str, List[List[float]]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
    
    def add_symbol(
        self,
        symbol: str,
        tier: SymbolTier,
        ohlcv_data: Optional[List[List[float]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add symbol to priority queue.
        
        Args:
            symbol: Trading symbol (e.g., AAPL, BTC/USD)
            tier: Priority tier
            ohlcv_data: Current OHLCV data (optional)
            metadata: Additional metadata (optional)
        """
        self._symbols[tier].add(symbol)
        
        if ohlcv_data:
            self._ohlcv_data[symbol] = ohlcv_data
        
        if metadata:
            self._metadata[symbol] = metadata
        
        # Never predict - force immediate prediction on next run
        self._last_prediction[symbol] = datetime.min
        
        logger.info(f"Added {symbol} to {tier.value} tier")
    
    def remove_symbol(self, symbol: str, tier: SymbolTier):
        """Remove symbol from tier."""
        self._symbols[tier].discard(symbol)
        self._ohlcv_data.pop(symbol, None)
        self._metadata.pop(symbol, None)
        self._last_prediction.pop(symbol, None)
        
        logger.info(f"Removed {symbol} from {tier.value} tier")
    
    def update_data(self, symbol: str, ohlcv_data: List[List[float]]):
        """Update OHLCV data for a symbol."""
        self._ohlcv_data[symbol] = ohlcv_data
    
    def get_symbols_due_prediction(self) -> List[str]:
        """
        Get symbols that are due for prediction.
        
        Returns:
            List of symbols that haven't been predicted within their tier interval
        """
        now = datetime.now()
        due_symbols = []
        
        for tier in SymbolTier:
            interval = self._tier_intervals[tier]
            symbols = self._symbols[tier]
            
            for symbol in symbols:
                last_pred = self._last_prediction.get(symbol, datetime.min)
                
                if now - last_pred >= interval:
                    due_symbols.append(symbol)
        
        # Sort by tier priority (Tier 1 first)
        tier_order = {tier.value: i for i, tier in enumerate(SymbolTier)}
        due_symbols.sort(key=lambda s: tier_order.get(
            self._get_symbol_tier(s),
            999
        ))
        
        logger.debug(f"{len(due_symbols)} symbols due for prediction")
        return due_symbols
    
    def _get_symbol_tier(self, symbol: str) -> Optional[SymbolTier]:
        """Get tier for a symbol."""
        for tier, symbols in self._symbols.items():
            if symbol in symbols:
                return tier
        return None
    
    def mark_predicted(self, symbol: str):
        """Mark symbol as predicted (reset timer)."""
        self._last_prediction[symbol] = datetime.now()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        now = datetime.now()
        
        due_by_tier = {}
        for tier in SymbolTier:
            interval = self._tier_intervals[tier]
            due_count = sum(
                1 for s in self._symbols[tier]
                if now - self._last_prediction.get(s, datetime.min) >= interval
            )
            due_by_tier[tier.value] = {
                "total": len(self._symbols[tier]),
                "due": due_count,
            }
        
        total_symbols = sum(len(symbols) for symbols in self._symbols.values())
        total_due = sum(d["due"] for d in due_by_tier.values())
        
        return {
            "total_symbols": total_symbols,
            "symbols_due": total_due,
            "by_tier": due_by_tier,
            "ohlcv_cached": len(self._ohlcv_data),
            "metadata_cached": len(self._metadata),
        }
    
    def get_tier_symbols(self, tier: SymbolTier) -> List[str]:
        """Get all symbols in a tier."""
        return list(self._symbols[tier])
    
    def promote_symbol(self, symbol: str, new_tier: SymbolTier):
        """
        Promote symbol to higher priority tier.
        
        Use when a Tier 3 candidate becomes a Tier 1 holding.
        """
        # Remove from all tiers
        for tier in SymbolTier:
            self._symbols[tier].discard(symbol)
        
        # Add to new tier
        self._symbols[new_tier].add(symbol)
        self._last_prediction[symbol] = datetime.min  # Force immediate prediction
        
        logger.info(f"Promoted {symbol} to {new_tier.value} tier")
    
    def clear_all(self):
        """Clear all symbols from queue."""
        for tier in SymbolTier:
            self._symbols[tier].clear()
        self._last_prediction.clear()
        
        logger.info("Cleared symbol priority queue")


# Global instance
symbol_priority_queue = SymbolPriorityQueue()


def get_symbol_priority_queue() -> SymbolPriorityQueue:
    """Get the symbol priority queue instance."""
    return symbol_priority_queue