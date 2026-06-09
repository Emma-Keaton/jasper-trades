"""
Trade Monitor - Tracks closed trades and stores experiences for learning
Sends WhatsApp notifications for trade events
"""
import structlog
from datetime import datetime
from typing import Optional
import asyncio

from app.database import async_session
from app.models import Trade
from app.services.experience_buffer import ExperienceBuffer, Experience
from app.services.pattern_analyzer import PatternAnalyzer
from app.services.whatsapp_service import whatsapp_service

logger = structlog.get_logger(__name__)


class TradeMonitor:
    """
    Monitors closed trades and converts them to learning experiences.
    Automatically retrains pattern model after accumulating new data.
    """
    
    def __init__(self):
        self.exp_buffer = ExperienceBuffer(capacity=1000)
        self.pattern_analyzer = PatternAnalyzer()
        self._last_training_size = len(self.exp_buffer.experiences)
        self._monitoring = False
        logger.info("TradeMonitor initialized")
    
    async def on_trade_closed(self, trade: Trade) -> None:
        """Called when a trade is closed - converts to experience"""
        logger.info(f"Trade closed: {trade.id} | {trade.symbol} | PnL: ${trade.pnl:.2f}")
        
        # Calculate outcome
        if trade.entry_price > 0:
            pnl_percent = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
        else:
            pnl_percent = 0
        
        # Calculate duration
        if trade.created_at and trade.filled_at:
            try:
                created = datetime.fromisoformat(trade.created_at.replace('Z', '+00:00'))
                filled = datetime.fromisoformat(trade.filled_at.replace('Z', '+00:00'))
                duration_minutes = int((filled - created).total_seconds() / 60)
            except:
                duration_minutes = 0
        else:
            duration_minutes = 0
        
        # Determine outcome
        if pnl_percent > 1.0:
            outcome = "WIN"
        elif pnl_percent < -1.0:
            outcome = "LOSS"
        else:
            outcome = "BREAKEVEN"
        
        # Create experience
        experience = Experience(
            trade_id=trade.id,
            symbol=trade.symbol,
            action=trade.type,  # BUY or SELL
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            shares=trade.shares,
            pnl=trade.pnl,
            pnl_percent=pnl_percent,
            hold_duration_minutes=duration_minutes,
            agent=trade.agent_name if hasattr(trade, 'agent_name') else "Unknown",
            market_conditions=trade.metadata.get("market_conditions", {}) if hasattr(trade, 'metadata') else {},
            technical_features=trade.metadata.get("technical_features", {}) if hasattr(trade, 'metadata') else {},
            outcome=outcome,
        )
        
        # Store experience
        self.exp_buffer.add(experience)
        
        # Check if we should retrain
        await self._maybe_retrain()
    
    async def _maybe_retrain(self) -> None:
        """Retrain pattern model if enough new experiences"""
        current_size = len(self.exp_buffer.experiences)
        
        # Retrain every 50 new experiences
        if current_size - self._last_training_size >= 50:
            logger.info(f"Retraining pattern model with {current_size} experiences...")
            
            # Run training in background to not block
            asyncio.create_task(self._retrain_model())
            self._last_training_size = current_size
    
    async def _retrain_model(self) -> bool:
        """Retrain the pattern analyzer"""
        success = self.pattern_analyzer.train_from_experiences(
            self.exp_buffer.experiences
        )
        
        if success:
            logger.info("Pattern model retrained successfully")
        else:
            logger.warning("Pattern model retraining failed or skipped")
        
        return success
    
    def get_learning_status(self) -> dict:
        """Get current learning system status"""
        recent_form = self.exp_buffer.get_recent_form(limit=20)
        winning_patterns = self.exp_buffer.get_winning_patterns(min_trades=5)
        training_status = self.pattern_analyzer.get_training_status()
        
        return {
            "total_experiences": len(self.exp_buffer.experiences),
            "recent_form": recent_form,
            "learning_enabled": True,
            "pattern_model": training_status,
            "win_rate": self.exp_buffer.win_stats["wins"] / max(self.exp_buffer.win_stats["total"], 1),
            "avg_pnl": self.exp_buffer.win_stats["total_pnl"] / max(self.exp_buffer.win_stats["total"], 1),
        }
    
    def predict_trade_success(
        self, 
        symbol: str, 
        market_conditions: dict, 
        technical_features: dict
    ) -> dict:
        """Get ML prediction for proposed trade"""
        prob, confidence = self.pattern_analyzer.predict_success_probability(
            market_conditions,
            technical_features
        )
        
        return {
            "symbol": symbol,
            "success_probability": prob,
            "confidence": confidence,
            "recommendation": "FAVORABLE" if prob > 0.55 else ("AVOID" if prob < 0.45 else "NEUTRAL"),
        }
    
    async def start_monitoring(self):
        """Start background monitoring loop"""
        self._monitoring = True
        logger.info("TradeMonitor started")
        
        while self._monitoring:
            await asyncio.sleep(60)  # Check every minute
            
            # Check for closed trades without experiences
            await self._sync_missing_experiences()
    
    async def _sync_missing_experiences(self):
        """Fetch closed trades and ensure they have experiences"""
        # This would query the database for trades without corresponding experiences
        # For now, it's a placeholder for future implementation
        pass
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        logger.info("TradeMonitor stopped")
    
    # Singleton instance
    _instance: Optional['TradeMonitor'] = None
    
    @classmethod
    def get_instance(cls) -> 'TradeMonitor':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global accessor
trade_monitor = TradeMonitor.get_instance()