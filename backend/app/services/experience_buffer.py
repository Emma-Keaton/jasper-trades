"""
Experience Buffer for Self-Learning AI
Stores trade experiences for pattern recognition and RL-based improvement
"""
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Experience:
    """Single trading experience tuple (state, action, outcome)"""
    trade_id: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    entry_price: float
    exit_price: Optional[float]
    shares: int
    pnl: float
    pnl_percent: float
    hold_duration_minutes: int
    agent: str
    market_conditions: Dict = field(default_factory=dict)
    technical_features: Dict = field(default_factory=dict)
    outcome: str = ""  # WIN, LOSS, BREAKEVEN
    lessons: List[str] = field(default_factory=list)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if not self.outcome:
            if self.pnl_percent > 1.0:
                self.outcome = "WIN"
            elif self.pnl_percent < -1.0:
                self.outcome = "LOSS"
            else:
                self.outcome = "BREAKEVEN"


class ExperienceBuffer:
    """
    Experience replay buffer for reinforcement learning.
    Stores last N trades and extracts patterns for improved decisions.
    """
    
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.experiences: List[Experience] = []
        self.db_path = Path("data/experiences.json")
        self.win_stats = {"total": 0, "wins": 0, "total_pnl": 0.0}
        self.load()
        logger.info(f"Experience buffer initialized with {len(self.experiences)} experiences")
    
    def add(self, experience: Experience) -> None:
        """Add experience, remove oldest if at capacity"""
        if len(self.experiences) >= self.capacity:
            removed = self.experiences.pop(0)
            logger.debug(f"Removed oldest experience: {removed.trade_id}")
        
        self.experiences.append(experience)
        
        # Update stats
        self.win_stats["total"] += 1
        if experience.outcome == "WIN":
            self.win_stats["wins"] += 1
        self.win_stats["total_pnl"] += experience.pnl
        
        # Extract lessons
        experience.lessons = self._extract_lessons(experience)
        
        self.save()
        logger.info(
            f"Added experience: {experience.trade_id} | "
            f"{experience.symbol} {experience.action} | "
            f"PnL: {experience.pnl_percent:.2f}% ({experience.outcome})"
        )
    
    def _extract_lessons(self, exp: Experience) -> List[str]:
        """Extract learning points from experience"""
        lessons = []
        
        if exp.outcome == "WIN" and exp.pnl_percent > 5:
            lessons.append(f"High confidence {exp.action} on {exp.symbol} worked well")
            if exp.market_conditions.get("vix", 0) < 20:
                lessons.append("Low VIX environment favored directional trades")
        
        elif exp.outcome == "LOSS" and exp.pnl_percent < -5:
            lessons.append(f"Avoid {exp.action} on {exp.symbol} in similar conditions")
            if exp.hold_duration_minutes > 240:
                lessons.append("Long hold times correlated with losses")
        
        # Pattern: RSI extremes
        rsi = exp.technical_features.get("rsi", 50)
        if exp.outcome == "WIN":
            if rsi < 30 and exp.action == "BUY":
                lessons.append("Oversold RSI (<30) + BUY = winning combo")
            elif rsi > 70 and exp.action == "SELL":
                lessons.append("Overbought RSI (>70) + SELL = winning combo")
        
        return lessons
    
    def get_winning_patterns(self, min_trades: int = 10) -> List[Dict]:
        """Extract patterns from winning trades"""
        winners = [e for e in self.experiences if e.outcome == "WIN" and e.pnl_percent > 2.0]
        
        if len(winners) < min_trades:
            return []
        
        patterns = []
        for exp in winners[:50]:  # Last 50 winners
            patterns.append({
                "symbol": exp.symbol,
                "action": exp.action,
                "market_vix": exp.market_conditions.get("vix", 0),
                "market_trend": exp.market_conditions.get("trend", "neutral"),
                "volume_ratio": exp.technical_features.get("volume_ratio", 1),
                "rsi": exp.technical_features.get("rsi", 50),
                "macd_signal": exp.technical_features.get("macd_signal", 0),
                "bb_position": exp.technical_features.get("bb_position", 0.5),
                "avg_pnl_percent": exp.pnl_percent,
                "hold_duration_minutes": exp.hold_duration_minutes,
                "time_of_day": exp.timestamp[11:13],  # Hour
            })
        
        # Cluster by RSI zones
        oversold_wins = [p for p in patterns if p["rsi"] < 30]
        overbought_wins = [p for p in patterns if p["rsi"] > 70]
        neutral_wins = [p for p in patterns if 30 <= p["rsi"] <= 70]
        
        return {
            "all_patterns": patterns,
            "oversold": oversold_wins,
            "overbought": overbought_wins,
            "neutral": neutral_wins,
            "win_rate": self.win_stats["wins"] / max(self.win_stats["total"], 1),
            "avg_pnl": self.win_stats["total_pnl"] / max(self.win_stats["total"], 1),
        }
    
    def get_losing_patterns(self, min_trades: int = 5) -> List[Dict]:
        """Extract patterns from losing trades to avoid"""
        losers = [e for e in self.experiences if e.outcome == "LOSS" and e.pnl_percent < -3.0]
        
        if len(losers) < min_trades:
            return []
        
        patterns = []
        for exp in losers[:30]:
            patterns.append({
                "symbol": exp.symbol,
                "action": exp.action,
                "market_vix": exp.market_conditions.get("vix", 0),
                "market_trend": exp.market_conditions.get("trend", "neutral"),
                "rsi": exp.technical_features.get("rsi", 50),
                "loss_percent": exp.pnl_percent,
                "hold_duration_minutes": exp.hold_duration_minutes,
            })
        
        return patterns
    
    def get_recent_form(self, limit: int = 20) -> Dict:
        """Get recent trading performance"""
        recent = self.experiences[-limit:]
        if not recent:
            return {"form": "unknown", "details": "No recent trades"}
        
        wins = sum(1 for e in recent if e.outcome == "WIN")
        losses = sum(1 for e in recent if e.outcome == "LOSS")
        win_rate = wins / len(recent)
        
        form = "HOT" if win_rate > 0.65 else ("COLD" if win_rate < 0.35 else "NEUTRAL")
        
        return {
            "form": form,
            "last_n": len(recent),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": sum(e.pnl for e in recent),
        }
    
    def save(self) -> None:
        """Persist experiences to disk"""
        self.db_path.parent.mkdir(exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump([asdict(e) for e in self.experiences], f, indent=2, default=str)
        logger.debug(f"Saved {len(self.experiences)} experiences to {self.db_path}")
    
    def load(self) -> None:
        """Load experiences from disk"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.experiences = [Experience(**d) for d in data]
                logger.info(f"Loaded {len(self.experiences)} experiences from disk")
            except Exception as e:
                logger.error(f"Failed to load experiences: {e}")
                self.experiences = []
    
    def clear(self) -> None:
        """Reset all experiences"""
        self.experiences = []
        self.win_stats = {"total": 0, "wins": 0, "total_pnl": 0.0}
        self.save()
        logger.info("Experience buffer cleared")