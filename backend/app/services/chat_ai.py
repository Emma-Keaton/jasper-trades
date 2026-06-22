"""
Chat AI Service
Conversational AI assistant for Telegram chat
Handles user queries about portfolio, trades, risk, and market

Enhanced with:
- Market status queries
- Recent trades history
- Trade brainstorming
- Agent decision explanations
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog
import json
import re

from app.nvidia_nim import nvidia_client
from app.services.portfolio_service import PortfolioService
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)


class ChatAI:
    """
    Chat AI - Conversational assistant for trading queries.

    Capabilities:
    - Portfolio status queries
    - Position details
    - Trade explanations
    - Risk metrics
    - Market status
    - Recent trades history
    - Trade brainstorming
    - Agent decision explanations
    - General conversation

    Uses NVIDIA NIM (Llama-3.2-3B) for fast, cheap responses.
    """

    def __init__(self, db_session):
        self.db = db_session
        self.model = "meta/llama-3.2-3b-instruct"  # Fast model for chat

    async def handle_message(self, phone: str, text: str) -> str:
        """
        Handle incoming Telegram message.

        Args:
            phone: User's phone number
            text: Message text

        Returns:
            AI response text
        """
        text = text.strip()

        # Detect intent
        intent = self._detect_intent(text)

        logger.info(f"Chat message", phone=phone, intent=intent, text=text[:50])

        # Handle commands
        if intent == 'status':
            return await self._handle_status()
        elif intent == 'positions':
            return await self._handle_positions()
        elif intent == 'explain_trade':
            symbol = self._extract_symbol(text)
            return await self._handle_explain_trade(symbol or 'AAPL')
        elif intent == 'risk':
            return await self._handle_risk()
        elif intent == 'market_status':
            return await self._handle_market_status()
        elif intent == 'recent_trades':
            return await self._handle_recent_trades()
        elif intent == 'brainstorm':
            return await self._handle_brainstorm(text)
        elif intent == 'agent_question':
            return await self._handle_agent_question(text)
        elif intent == 'help':
            return self._handle_help()
        else:
            # General conversation
            return await self._handle_conversation(text)

    def _detect_intent(self, text: str) -> str:
        """
        Detect user intent from message.

        Intents:
        - status: Portfolio value, PnL
        - positions: Current holdings
        - explain_trade: Why did you buy/sell X
        - risk: Risk metrics
        - market_status: Is market open, market hours
        - recent_trades: What trades did you make today
        - brainstorm: Should I buy X, what do you think about Y
        - agent_question: Which agent made this trade
        - help: What can you do
        - conversation: Everything else
        """
        text_lower = text.lower()

        # Market status
        if any(word in text_lower for word in ['market open', 'market close', 'market hours', 'is market', 'market status', 'trading hours']):
            return 'market_status'

        # Recent trades
        if any(word in text_lower for word in ['recent trade', 'today trade', 'made today', 'trades today', 'what did you buy', 'what did you sell', 'latest trade']):
            return 'recent_trades'

        # Brainstorming / opinion
        if any(word in text_lower for word in ['should i buy', 'should i sell', 'what do you think', 'is it good', 'worth buying', 'worth selling', 'brainstorm', 'tell me about', 'opinion on']):
            return 'brainstorm'

        # Agent questions
        if any(word in text_lower for word in ['which agent', 'why did you buy', 'why did you sell', 'who made', 'agent decision', 'why this trade']):
            return 'agent_question'

        # Status queries
        if any(word in text_lower for word in ['status', 'portfolio', 'value', 'balance', 'pnl', 'profit', 'loss', 'account']):
            return 'status'

        # Position queries
        if any(word in text_lower for word in ['position', 'holding', 'own', 'have', 'portfolio']):
            return 'positions'

        # Trade explanation
        if any(word in text_lower for word in ['why', 'explain', 'reason', 'bought', 'sold', 'trade']):
            return 'explain_trade'

        # Risk queries
        if any(word in text_lower for word in ['risk', 'var', 'drawdown', 'exposure']):
            return 'risk'

        # Help
        if any(word in text_lower for word in ['help', 'what can', 'features', 'commands']):
            return 'help'

        return 'conversation'

    def _extract_symbol(self, text: str) -> Optional[str]:
        """Extract trading symbol from text."""
        words = text.upper().split()
        for word in words:
            cleaned = re.sub(r'[^A-Z]', '', word)
            if len(cleaned) >= 2 and len(cleaned) <= 5:
                return cleaned
        return None

    async def _handle_status(self) -> str:
        """Handle portfolio status query."""
        try:
            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()

            if not portfolios:
                return "I couldn't find any portfolio in your account."

            portfolio = portfolios[0]
            summary = await portfolio_service.get_portfolio_summary(portfolio.id)

            total_value = summary.get('total_value', 0)
            initial_value = summary.get('initial_value', 0)
            return_value = total_value - initial_value
            return_pct = (return_value / initial_value * 100) if initial_value > 0 else 0

            cash = summary.get('cash', 0)
            market_value = summary.get('market_value', 0)

            message = (
                f"📊 *Portfolio Summary*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Total Value: ${total_value:,.2f}\n"
                f"💵 Cash: ${cash:,.2f}\n"
                f"📈 Holdings: ${market_value:,.2f}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 Return: ${return_value:+,.2f} ({return_pct:+.2f}%)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Type: {'Paper' if portfolio.is_paper else 'Live'} Trading"
            )

            return message

        except Exception as e:
            logger.error(f"Status query error: {e}")
            return "Sorry, I couldn't retrieve your portfolio status right now."

    async def _handle_positions(self) -> str:
        """Handle positions query."""
        try:
            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()

            if not portfolios:
                return "I couldn't find any portfolio."

            positions = await portfolio_service.get_all_positions(portfolios[0].id)

            if not positions:
                return "You don't have any open positions right now."

            message = "📊 *Current Positions*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"

            for pos in positions[:5]:
                pnl = pos.unrealized_pnl or 0
                pnl_pct = pos.unrealized_pnl_percent or 0
                emoji = "🟢" if pnl >= 0 else "🔴"

                message += f"{emoji} {pos.symbol}\n"
                message += f"  Qty: {pos.quantity} | Price: ${pos.current_price:.2f}\n"
                message += f"  PnL: ${pnl:+,.2f} ({pnl_pct:+.1%})\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n"

            if len(positions) > 5:
                message += f"_...and {len(positions) - 5} more positions_\n"

            return message

        except Exception as e:
            logger.error(f"Positions query error: {e}")
            return "Sorry, I couldn't retrieve your positions right now."

    async def _handle_explain_trade(self, symbol: str) -> str:
        """Handle trade explanation query."""
        try:
            from sqlalchemy import select
            from app.models import Trade

            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()

            if not portfolios:
                return "No portfolio found."

            query = select(Trade).where(
                Trade.symbol == symbol.upper(),
                Trade.status == 'filled'
            ).order_by(Trade.created_at.desc()).limit(5)

            result = await self.db.execute(query)
            trades = list(result.scalars().all())

            if not trades:
                return f"No recent trades found for {symbol}."

            trade_context = "\n".join([
                f"- {t.type} {t.shares} {t.symbol} @ ${t.price:.2f} on {t.created_at.strftime('%m/%d %H:%M')} | Agent: {t.agent_name or 'AI'}"
                for t in trades
            ])

            prompt = f"""
User is asking about recent trades for {symbol}.

Recent trades:
{trade_context}

Provide a concise explanation in 2-3 sentences:
1. What was the trading thesis
2. Which agent initiated it (if known)
3. Current status

Keep it conversational and informative.
"""

            messages = [
                {"role": "system", "content": "You are Jasper, a helpful trading assistant."},
                {"role": "user", "content": prompt}
            ]

            response = await nvidia_client.chat_completion(messages, task_type='analysis')

            message = f"📈 *{symbol} Trade Analysis*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"
            message += response.strip()
            message += "\n\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"_{len(trades)} recent trade(s)_"

            return message

        except Exception as e:
            logger.error(f"Trade explanation error: {e}")
            return f"Sorry, I couldn't analyze {symbol} trades right now."

    async def _handle_risk(self) -> str:
        """Handle risk metrics query."""
        return (
            "🛡️ *Risk Metrics*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Your portfolio risk is being monitored in real-time.\n\n"
            "📊 Key Metrics:\n"
            "• VaR (95%): Max 1-day loss threshold\n"
            "• Drawdown: Monitored vs peak value\n"
            "• Sharpe Ratio: Risk-adjusted returns\n\n"
            "⚠️ Circuit breaker is active and protecting your portfolio from extreme market conditions.\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Ask for 'portfolio status' for current value."
        )

    async def _handle_market_status(self) -> str:
        """Handle market status query."""
        now = datetime.utcnow()
        is_weekend = now.weekday() >= 5
        hour = now.hour
        
        # Simple US market hours check (9:30 AM - 4:00 PM ET)
        is_market_open = not is_weekend and 13 <= hour < 21  # ET is UTC-4/5, approx
        
        status = "🟢 OPEN" if is_market_open else "🔴 CLOSED"
        next_open = "9:30 AM ET" if is_weekend or hour >= 21 else "9:30 AM ET (next trading day)"
        
        return (
            f"📊 *Market Status*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"US Stock Market: {status}\n\n"
            f"Trading Hours: 9:30 AM - 4:00 PM ET\n"
            f"Next Open: {next_open}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Crypto markets trade 24/7.\n"
            f"Forex trades Sunday 5 PM - Friday 5 PM ET."
        )

    async def _handle_recent_trades(self) -> str:
        """Handle recent trades query."""
        try:
            from sqlalchemy import select
            from app.models import Trade

            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()

            if not portfolios:
                return "No portfolio found."

            query = select(Trade).where(
                Trade.status == 'filled'
            ).order_by(Trade.created_at.desc()).limit(10)

            result = await self.db.execute(query)
            trades = list(result.scalars().all())

            if not trades:
                return "No recent trades found."

            message = "📜 *Recent Trades*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"

            for t in trades[:5]:
                pnl_emoji = "🟢" if (t.pnl or 0) > 0 else "🔴" if (t.pnl or 0) < 0 else "➖"
                pnl_text = f"${t.pnl:+,.2f}" if t.pnl is not None else "Open"
                
                message += f"{pnl_emoji} {t.symbol} {t.side.upper()}\n"
                message += f"  {t.shares} @ ${t.price:.2f}\n"
                message += f"  {pnl_text}\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n"

            return message

        except Exception as e:
            logger.error(f"Recent trades error: {e}")
            return "Sorry, I couldn't retrieve your recent trades."

    async def _handle_brainstorm(self, text: str) -> str:
        """Handle brainstorming/query about symbol."""
        try:
            symbol = self._extract_symbol(text) or 'AAPL'
            
            # Get portfolio context
            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()
            portfolio_ctx = ""
            
            if portfolios:
                summary = await portfolio_service.get_portfolio_summary(portfolios[0].id)
                portfolio_ctx = f"""
User's portfolio context:
- Total Value: ${summary.get('total_value', 0):,.2f}
- Cash Available: ${summary.get('cash', 0):,.2f}
- Current Return: {summary.get('total_return_percent', 0):.1f}%
"""

            prompt = f"""
User is asking for advice about {symbol}.

Question: "{text}"

{portfolio_ctx}

Provide a balanced, informative response:
1. Current market sentiment (if known)
2. Key factors to consider
3. Risk considerations
4. NOT financial advice disclaimer

Keep it concise (3-5 sentences) and conversational.
"""

            messages = [
                {"role": "system", "content": "You are Jasper, a helpful AI trading assistant. Provide balanced analysis, NOT financial advice."},
                {"role": "user", "content": prompt}
            ]

            response = await nvidia_client.chat_completion(messages, task_type='analysis')

            message = f"💡 *{symbol} Analysis*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"
            message += response.strip()
            message += "\n\n━━━━━━━━━━━━━━━━━━━━\n"
            message += "_⚠️ Not financial advice. Do your own research._"

            return message

        except Exception as e:
            logger.error(f"Brainstorm error: {e}")
            return "Sorry, I couldn't analyze that right now. Try asking about a specific symbol."

    async def _handle_agent_question(self, text: str) -> str:
        """Handle agent decision explanation query."""
        try:
            from sqlalchemy import select
            from app.models import Trade, DecisionLog

            symbol = self._extract_symbol(text)

            # Get recent trades with agent info
            query = select(Trade).where(
                Trade.agent_name.isnot(None)
            ).order_by(Trade.created_at.desc()).limit(5)

            if symbol:
                query = query.where(Trade.symbol == symbol.upper())

            result = await self.db.execute(query)
            trades = list(result.scalars().all())

            if not trades:
                # Try decision logs
                log_query = select(DecisionLog).order_by(DecisionLog.created_at.desc()).limit(5)
                if symbol:
                    log_query = log_query.where(DecisionLog.symbol == symbol.upper())

                log_result = await self.db.execute(log_query)
                decisions = list(log_result.scalars().all())

                if not decisions:
                    return "No agent decisions found. Trades may be executed automatically without specific agent attribution."

                message = "🤖 *Recent Agent Decisions*\n\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n"

                for d in decisions[:3]:
                    message += f"• {d.symbol}: {d.action.upper()}\n"
                    message += f"  Agent: {d.agent_name or 'AI'}\n"
                    message += f"  Confidence: {d.confidence:.0%}\n"
                    message += f"  Reason: {d.reasoning[:80]}...\n"
                    message += "━━━━━━━━━━━━━━━━━━━━\n"

                return message

            message = f"🤖 *Agent Trade Decisions*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"

            for t in trades[:5]:
                message += f"• {t.symbol}: {t.side.upper()} {t.shares}\n"
                message += f"  Agent: {t.agent_name or 'AI'}\n"
                message += f"  @ ${t.price:.2f}\n"
                if t.pnl is not None:
                    pnl_emoji = "🟢" if t.pnl > 0 else "🔴" if t.pnl < 0 else "➖"
                    message += f"  {pnl_emoji} PnL: ${t.pnl:+,.2f}\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n"

            return message

        except Exception as e:
            logger.error(f"Agent question error: {e}")
            return "Sorry, I couldn't retrieve agent decision information right now."

    def _handle_help(self) -> str:
        """Handle help command."""
        return (
            "🤖 *Jasper Chat Assistant*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "I can help you with:\n\n"
            "📊 *Portfolio* - 'status', 'my portfolio', 'account value'\n"
            "📈 *Positions* - 'what do I own', 'my holdings'\n"
            "🔍 *Trade Analysis* - 'why did you buy NVDA', 'explain TSLA trade'\n"
            "🕐 *Market Status* - 'is market open', 'market hours'\n"
            "📜 *Recent Trades* - 'what trades today', 'recent trades'\n"
            "💡 *Brainstorming* - 'should I buy AAPL', 'what do you think about TSLA'\n"
            "🤖 *Agent Info* - 'which agent made this trade', 'agent decisions'\n"
            "🛡️ *Risk* - 'risk metrics', 'drawdown'\n"
            "💬 *General Chat* - Ask me anything about your portfolio!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Just ask naturally! I understand context."
        )

    async def _handle_conversation(self, text: str) -> str:
        """Handle general conversation."""
        try:
            portfolio_service = PortfolioService(self.db)
            portfolios = await portfolio_service.get_portfolios()

            portfolio_ctx = ""
            if portfolios:
                summary = await portfolio_service.get_portfolio_summary(portfolios[0].id)
                portfolio_ctx = f"""
Context about user's portfolio:
- Total Value: ${summary.get('total_value', 0):,.2f}
- Cash: ${summary.get('cash', 0):,.2f}
- Holdings Value: ${summary.get('market_value', 0):,.2f}
- Return: {summary.get('total_return_percent', 0):.1f}%
- Positions: {summary.get('positions_count', 0)}
"""

            prompt = f"""
You are Jasper, an AI trading assistant for Jasper Trades platform.

User message: "{text}"

{portfolio_ctx}

Respond conversationally and helpful:
- If asking about trading, be informative but cautious (not financial advice)
- If asking about their portfolio, use the context above
- Keep responses concise (2-4 sentences for chat)
- Use emoji sparingly if appropriate
"""

            messages = [
                {"role": "system", "content": "You are Jasper, a friendly AI trading assistant."},
                {"role": "user", "content": prompt}
            ]

            response = await nvidia_client.chat_completion(messages, task_type='analysis')
            return response.strip()

        except Exception as e:
            logger.error(f"Conversation error: {e}")
            return "Sorry, I didn't quite catch that. Try asking about your portfolio or trades!"


# Factory function
def get_chat_ai(db_session) -> ChatAI:
    """Create ChatAI instance with database session."""
    return ChatAI(db_session)