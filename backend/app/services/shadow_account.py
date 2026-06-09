"""
Vibe-Trading Shadow Account
Analyzes user's historical trades to detect patterns and generate "trading fingerprint".

Features:
- Trade pattern analysis (win/loss timing, position sizing)
- Risk preference detection
- Favorite sectors/themes
- Trading fingerprint generation
- Inject insights into agent prompts
"""
from typing import Dict, Any, Optional, List
from sqlalchemy import select, func
from datetime import datetime, timedelta
import structlog
import json

from app.database import async_session
from app.models import Trade

logger = structlog.get_logger(__name__)


class ShadowAccountService:
    """
    Vibe-Trading style Shadow Account analysis.
    
    Analyzes user's historical trades to understand their:
    - Trading style (scalper, day trader, swing, position)
    - Risk tolerance (conservative, moderate, aggressive)
    - Win patterns (what works)
    - Loss patterns (what doesn't work)
    - Sector/theme preferences
    - Position sizing habits
    """
    
    async def analyze_trading_style(self, portfolio_id: int = 1) -> Dict[str, Any]:
        """
        Analyze user's historical trades to determine trading style.
        
        Returns:
            TradingStyle object with detected patterns
        """
        async with async_session() as session:
            # Get all historical trades
            result = await session.execute(
                select(Trade)
                .filter(Trade.portfolio_id == portfolio_id)
                .filter(Trade.status == "filled")
                .order_by(Trade.created_at.desc())
            )
            trades = list(result.scalars().all())
            
            if len(trades) == 0:
                return self._empty_style()
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
            
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = win_count / total_trades if total_trades > 0 else 0
            
            # Average hold time (for executed trades with exit)
            hold_times = []
            for trade in trades:
                if trade.exit_price and trade.created_at:
                    # Approximate hold time from created to now (or exit)
                    hold_time = (datetime.utcnow() - trade.created_at).total_seconds() / 3600
                    hold_times.append(hold_time)
            
            avg_hold_time_hours = sum(hold_times) / len(hold_times) if hold_times else 0
            
            # Average position size
            avg_position_size = sum(t.quantity for t in trades) / total_trades if trades else 0
            
            # Risk tolerance (based on position sizing and trade frequency)
            if avg_position_size > 100 or total_trades > 50:
                risk_tolerance = "aggressive"
            elif avg_position_size > 50 or total_trades > 20:
                risk_tolerance = "moderate"
            else:
                risk_tolerance = "conservative"
            
            # Trading style based on hold time
            if avg_hold_time_hours < 2:
                style = "scalper"
            elif avg_hold_time_hours < 24:
                style = "day_trader"
            elif avg_hold_time_hours < 168:  # 1 week
                style = "swing_trader"
            else:
                style = "position_trader"
            
            # Sector/theme analysis
            symbols = [t.symbol for t in trades]
            symbol_counts = {}
            for s in symbols:
                symbol_counts[s] = symbol_counts.get(s, 0) + 1
            
            favorite_sectors = self._infer_sectors(list(symbol_counts.keys())[:5])
            
            # Pattern strengths
            strengths = []
            if win_rate > 0.6:
                strengths.append("High win rate trading")
            if avg_hold_time_hours > 100 and win_rate > 0.5:
                strengths.append("Patient position holding")
            if total_trades > 30:
                strengths.append("Active trading discipline")
            
            # Pattern weaknesses
            weaknesses = []
            if win_rate < 0.4:
                weaknesses.append("Low win rate - review entry criteria")
            if avg_hold_time_hours < 1 and win_rate < 0.5:
                weaknesses.append("Overtrading - consider longer timeframes")
            if len(set(symbols)) < 5 and total_trades > 20:
                weaknesses.append("Concentration risk - diversify holdings")
            
            trading_style = {
                "style": style,
                "avg_hold_time_hours": round(avg_hold_time_hours, 2),
                "win_rate": round(win_rate, 3),
                "total_trades": total_trades,
                "risk_tolerance": risk_tolerance,
                "avg_position_size": round(avg_position_size, 2),
                "favorite_symbols": list(symbol_counts.keys())[:5],
                "favorite_sectors": favorite_sectors,
                "pattern_strengths": strengths,
                "pattern_weaknesses": weaknesses,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Analyzed trading style: {style}, {total_trades} trades")
            return trading_style
    
    async def get_trading_fingerprint(self, portfolio_id: int = 1) -> str:
        """
        Generate a compact "trading fingerprint" summary for agent prompts.
        
        Returns:
            Natural language description of user's trading style
        """
        style = await self.analyze_trading_style(portfolio_id)
        
        fingerprint = (
            f"User is a {style['risk_tolerance']} {style['style']} with "
            f"{style['total_trades']} historical trades. "
            f"Win rate: {style['win_rate']:.1%}. "
            f"Average hold time: {style['avg_hold_time_hours']:.1f} hours. "
            f"Favorites: {', '.join(style['favorite_symbols'][:3])}. "
        )
        
        if style['pattern_strengths']:
            fingerprint += f"Strengths: {style['pattern_strengths'][0]}. "
        
        if style['pattern_weaknesses']:
            fingerprint += f"Watch out for: {style['pattern_weaknesses'][0]}."
        
        return fingerprint
    
    async def get_personalized_agent_prompt(
        self,
        portfolio_id: int = 1,
        base_prompt: Optional[str] = None
    ) -> str:
        """
        Get personalized prompt for AI agents incorporating user's trading style.
        
        Args:
            portfolio_id: Portfolio to analyze
            base_prompt: Base prompt to enhance
        
        Returns:
            Enhanced prompt with user context
        """
        fingerprint = await self.get_trading_fingerprint(portfolio_id)
        
        context = (
            f"User Trading Profile: {fingerprint}\n\n"
            f"Consider the user's trading style and preferences when providing advice. "
            f"If the user tends to overtrade, suggest patience. "
            f"If win rate is low, suggest reviewing entry criteria. "
            f"Leverage their strengths in your recommendations.\n\n"
        )
        
        if base_prompt:
            return context + base_prompt
        
        return context
    
    def _empty_style(self) -> Dict[str, Any]:
        """Return empty style dict when no trades exist."""
        return {
            "style": "unknown",
            "avg_hold_time_hours": 0,
            "win_rate": 0,
            "total_trades": 0,
            "risk_tolerance": "unknown",
            "avg_position_size": 0,
            "favorite_symbols": [],
            "favorite_sectors": [],
            "pattern_strengths": ["No trading history yet"],
            "pattern_weaknesses": [],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _infer_sectors(self, symbols: List[str]) -> List[str]:
        """Infer sectors from symbols (simplified)."""
        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "NVDA": "Technology/Semiconductors",
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "TSLA": "Consumer Discretionary/Auto",
            "META": "Technology",
            "JPM": "Financials",
            "BAC": "Financials",
            "GS": "Financials",
            "JNJ": "Healthcare",
            "PFE": "Healthcare",
            "UNH": "Healthcare",
            "XOM": "Energy",
            "CVX": "Energy",
            "SPY": "Broad Market",
            "QQQ": "Technology",
            "IWM": "Small-Cap"
        }
        
        sectors = set()
        for symbol in symbols:
            sector = sector_map.get(symbol.upper(), "Other")
            sectors.add(sector)
        
        return list(sectors)[:5]


# Global instance
shadow_account_service = ShadowAccountService()