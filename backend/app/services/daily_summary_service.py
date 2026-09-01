"""
Daily Summary Service
Generates and sends end-of-day trade summaries via WhatsApp
Scheduled to run at 8:00 PM WAT (West Africa Time, UTC+1)
"""
import structlog
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailySummary, TelegramUser, Trade, Portfolio
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)


class DailySummaryService:
    """
    Daily Summary Service - Generates and sends WhatsApp summaries.
    
    Features:
    - Calculates daily PnL, win rate, trade stats
    - Identifies best/worst trades
    - Agent performance breakdown
    - Top symbols traded
    - Sends via WhatsApp at scheduled time (8 PM WAT default)
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def generate_summary(
        self,
        portfolio_id: int,
        device_id: str,
        date: str,
    ) -> Optional[DailySummary]:
        """
        Generate daily summary for a portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            device_id: Device fingerprint
            date: ISO format date string (YYYY-MM-DD)
            
        Returns:
            DailySummary object or None if no trades
        """
        logger.info(f"Generating daily summary", portfolio_id=portfolio_id, date=date)
        
        # Parse date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return None
        
        # Fetch all trades for the day
        query = select(Trade).where(
            and_(
                Trade.created_at >= start_datetime,
                Trade.created_at <= end_datetime,
            )
        )
        
        result = await self.db.execute(query)
        trades = list(result.scalars().all())
        
        if not trades:
            logger.info(f"No trades found for portfolio {portfolio_id} on {date}")
            return None
        
        # Calculate statistics
        portfolio_value = 10000.0
        try:
            pv_result = await self.db.execute(select(Portfolio).limit(1))
            pv_portfolio = pv_result.scalar_one_or_none()
            if pv_portfolio and pv_portfolio.cash:
                portfolio_value = pv_portfolio.cash
        except Exception:
            pass
        stats = self._calculate_statistics(trades, portfolio_value)
        
        if stats['total_trades'] == 0:
            return None
        
        # Get user's Telegram chat ID
        user_query = select(TelegramUser).where(
            TelegramUser.device_id == device_id
        )
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user or not user.chat_id:
            logger.warning(f"No Telegram user found for device {device_id}")
            return None
        
        # Create summary record
        summary = DailySummary(
            portfolio_id=portfolio_id,
            device_id=device_id,
            chat_id=user.chat_id,
            summary_date=date,
            total_pnl=stats['total_pnl'],
            total_pnl_percent=stats['total_pnl_percent'],
            total_trades=stats['total_trades'],
            wins=stats['wins'],
            losses=stats['losses'],
            breakeven=stats['breakeven'],
            win_rate=stats['win_rate'],
            best_trade=stats['best_trade'],
            worst_trade=stats['worst_trade'],
            agent_stats=stats['agent_stats'],
            top_symbols=stats['top_symbols'],
            summary_sent=False,
            send_time_wat=user.summary_time_wat or "20:00",
        )
        
        self.db.add(summary)
        await self.db.commit()
        await self.db.refresh(summary)
        
        logger.info(
            f"Daily summary generated",
            summary_id=summary.id,
            total_pnl=stats['total_pnl'],
            win_rate=stats['win_rate']
        )
        
        return summary
    
    def _calculate_statistics(self, trades: List[Trade], portfolio_value: float = 10000.0) -> Dict:
        """Calculate trade statistics."""
        total_pnl = 0.0
        wins = 0
        losses = 0
        breakeven = 0
        best_trade = None
        worst_trade = None
        agent_stats = {}
        symbol_stats = {}
        
        for trade in trades:
            # Calculate PnL
            pnl = trade.pnl or 0.0
            pnl_percent = trade.pnl_percent or 0.0
            total_pnl += pnl
            
            # Determine outcome
            if pnl > 0.5:  # Win threshold (>$0.50)
                wins += 1
                outcome = 'win'
            elif pnl < -0.5:  # Loss threshold
                losses += 1
                outcome = 'loss'
            else:
                breakeven += 1
                outcome = 'breakeven'
            
            # Track best/worst trades
            if best_trade is None or pnl > best_trade['pnl']:
                best_trade = {
                    'symbol': trade.symbol,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'action': trade.side.upper(),
                    'shares': trade.quantity,
                }
            
            if worst_trade is None or pnl < worst_trade['pnl']:
                worst_trade = {
                    'symbol': trade.symbol,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'action': trade.side.upper(),
                    'shares': trade.quantity,
                }
            
            # Agent performance
            agent_name = trade.agent_name or 'Unknown'
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {
                    'agent_name': agent_name,
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'pnl': 0.0,
                }
            
            agent_stats[agent_name]['trades'] += 1
            agent_stats[agent_name]['pnl'] += pnl
            if outcome == 'win':
                agent_stats[agent_name]['wins'] += 1
            elif outcome == 'loss':
                agent_stats[agent_name]['losses'] += 1
            
            # Symbol statistics
            symbol = trade.symbol
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'symbol': symbol,
                    'trades': 0,
                    'pnl': 0.0,
                }
            
            symbol_stats[symbol]['trades'] += 1
            symbol_stats[symbol]['pnl'] += pnl
        
        # Calculate win rate
        total_trades = len(trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        # Calculate total PnL percent based on actual portfolio value
        total_pnl_percent = (total_pnl / portfolio_value * 100) if portfolio_value > 0 else 0.0
        
        # Get top symbols by trade count
        top_symbols = sorted(
            symbol_stats.values(),
            key=lambda x: x['trades'],
            reverse=True
        )[:5]  # Top 5 symbols
        
        return {
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_percent,
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': win_rate,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'agent_stats': list(agent_stats.values()),
            'top_symbols': top_symbols,
        }
    
    async def send_summary(self, summary: DailySummary) -> bool:
        """
        Send daily summary via Telegram.
        
        Args:
            summary: DailySummary object
            
        Returns:
            True if sent successfully
        """
        if not summary.chat_id:
            logger.error("No phone number in summary")
            return False
        
        # Format message
        message = self._format_summary_message(summary)
        
        # Send via WhatsApp
        success = await telegram_service.send_daily_summary(summary.chat_id, message)
        
        if success:
            # Update summary record
            summary.summary_sent = True
            summary.sent_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(
                f"Daily summary sent",
                summary_id=summary.id,
                phone=summary.chat_id[:5] + "***"
            )
        else:
            logger.error(f"Failed to send daily summary", summary_id=summary.id)
        
        return success
    
    def _format_summary_message(self, summary: DailySummary) -> str:
        """Format summary into WhatsApp message."""
        
        # Determine emoji based on performance
        if summary.total_pnl > 0:
            emoji = "🟢"
            outcome = "PROFIT"
        elif summary.total_pnl < 0:
            emoji = "🔴"
            outcome = "LOSS"
        else:
            emoji = "➖"
            outcome = "BREAKEVEN"
        
        # Format date
        try:
            date_obj = datetime.strptime(summary.summary_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %b %d, %Y")
        except:
            formatted_date = summary.summary_date
        
        # Build agent stats text
        agent_text = ""
        if summary.agent_stats:
            for agent in sorted(summary.agent_stats, key=lambda x: x.get('pnl', 0), reverse=True)[:3]:
                agent_emoji = "🟢" if agent.get('pnl', 0) > 0 else "🔴" if agent.get('pnl', 0) < 0 else "➖"
                agent_text += f"  {agent_emoji} {agent.get('agent_name', 'Unknown')}: ${agent.get('pnl', 0):+.2f} ({agent.get('trades', 0)} trades)\n"
        else:
            agent_text = "  No agent data available\n"
        
        # Format best/worst trades
        best_text = "N/A"
        if summary.best_trade:
            bt = summary.best_trade
            best_text = f"{bt.get('symbol', 'N/A')} {bt.get('action', 'N/A')} ${bt.get('pnl', 0):+.2f}"
        
        worst_text = "N/A"
        if summary.worst_trade:
            wt = summary.worst_trade
            worst_text = f"{wt.get('symbol', 'N/A')} {wt.get('action', 'N/A')} ${wt.get('pnl', 0):+.2f}"
        
        message = f"""
{emoji} *DAILY SUMMARY - {outcome}*
━━━━━━━━━━━━━━━━━━━━
📅 {formatted_date}

💰 **Total PnL:** ${summary.total_pnl:+,.2f}
📈 **Return:** {summary.total_pnl_percent:+.2f}%
📊 **Win Rate:** {summary.win_rate:.1f}% ({summary.wins}W / {summary.losses}L / {summary.breakeven}BE)
🎯 **Trades:** {summary.total_trades}

🏆 *Best Trade:*
  {best_text}

📉 *Worst Trade:*
  {worst_text}

🤖 *Agent Performance:*
{agent_text}
━━━━━━━━━━━━━━━━━━━━
📊 Type *STATUS* for portfolio
📈 Type *TRADES* for today's trades
💬 Type *HELP* for commands
"""
        
        return message
    
    async def send_summaries_for_date(self, date: str) -> int:
        """
        Send all pending summaries for a given date.
        
        Args:
            date: ISO format date string
            
        Returns:
            Number of summaries sent
        """
        # Get unsent summaries for the date
        query = select(DailySummary).where(
            and_(
                DailySummary.summary_date == date,
                DailySummary.summary_sent == False,
            )
        )
        
        result = await self.db.execute(query)
        summaries = list(result.scalars().all())
        
        sent_count = 0
        for summary in summaries:
            success = await self.send_summary(summary)
            if success:
                sent_count += 1
        
        return sent_count
    
    async def get_todays_summary(self, portfolio_id: int) -> Optional[DailySummary]:
        """Get today's summary for a portfolio."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        query = select(DailySummary).where(
            and_(
                DailySummary.portfolio_id == portfolio_id,
                DailySummary.summary_date == today,
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_recent_summaries(self, device_id: str, limit: int = 7) -> List[DailySummary]:
        """Get recent summaries for a device."""
        query = select(DailySummary).where(
            DailySummary.device_id == device_id
        ).order_by(
            DailySummary.summary_date.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


# Factory function
def get_daily_summary_service(db_session: AsyncSession) -> DailySummaryService:
    """Create DailySummaryService instance."""
    return DailySummaryService(db_session)