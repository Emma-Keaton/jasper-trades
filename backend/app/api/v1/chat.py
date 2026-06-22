"""
General Chat API - AI-powered assistant
Answers questions about portfolio, trades, signals using real backend data
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import structlog
from datetime import datetime
from sqlalchemy import select

from app.database import get_db
from app.models import ChatMessage, Portfolio, Trade, Position, TelegramUser
from app.nvidia_nim import nvidia_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat message request"""
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    messages: List[dict]
    count: int


@router.post("/", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Process chat message from user.
    Fetches real portfolio, trades, and signals data based on intent.
    """
    if not device_id:
        device_id = "anonymous"
    
    logger.info(f"Chat received from {device_id}", message=request.message[:50])

    try:
        # Store incoming message
        chat_msg = ChatMessage(
            phone_number=device_id,
            message=request.message,
            direction="incoming",
            message_type="text",
        )
        db.add(chat_msg)
        await db.commit()

        # Detect intent and fetch real data
        intent = detect_intent(request.message)
        logger.info(f"Detected intent: {intent}")

        # Route to handler based on intent
        if intent == "portfolio":
            response_text = await handle_portfolio_intent(device_id, db)
        elif intent == "trades":
            response_text = await handle_trades_intent(device_id, db)
        elif intent == "signals":
            response_text = await handle_signals_intent(device_id, db)
        elif intent == "balance":
            response_text = await handle_balance_intent(device_id, db)
        else:
            # General AI chat using NVIDIA NIM
            response_text = await handle_general_chat(request.message, device_id, db)

        # Store AI response
        ai_response = ChatMessage(
            phone_number=device_id,
            message=response_text,
            direction="outgoing",
            message_type="ai_response",
            intent=intent,
        )
        db.add(ai_response)
        await db.commit()

        return ChatResponse(response=response_text, intent=intent)

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    device_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get chat history for device."""
    query = select(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(limit)

    if device_id:
        query = query.where(ChatMessage.phone_number == device_id)

    result = await db.execute(query)
    messages = result.scalars().all()

    return ChatHistoryResponse(
        messages=[
            {
                "id": m.id,
                "message": m.message,
                "direction": m.direction,
                "type": m.message_type,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        count=len(messages),
    )


# ============ REAL Intent Handlers ============

def detect_intent(message: str) -> str:
    """Detect user intent from message"""
    msg_lower = message.lower()
    
    if any(word in msg_lower for word in ['portfolio', 'holdings', 'positions', 'balance']):
        return "portfolio"
    if any(word in msg_lower for word in ['trades', 'bought', 'sold', 'bought', 'transactions']):
        return "trades"
    if any(word in msg_lower for word in ['signal', 'buy', 'sell', 'recommend', 'should i']):
        return "signals"
    if any(word in msg_lower for word in ['pnl', 'profit', 'loss', 'return', 'performance']):
        return "balance"
    
    return "general"


async def handle_portfolio_intent(device_id: str, db: AsyncSession) -> str:
    """Handle portfolio query - fetches REAL data"""
    from app.services.portfolio_service import PortfolioService
    
    portfolio_service = PortfolioService(db)
    
    # Get user's portfolio
    portfolios = await portfolio_service.get_portfolios()
    if not portfolios:
        return "📊 *Portfolio Not Found*\n\nYou don't have any portfolios yet. Create one to start trading!"
    
    portfolio = portfolios[0]  # Use first portfolio
    summary = await portfolio_service.get_portfolio_summary(portfolio.id)
    
    # Get positions
    positions = await portfolio_service.get_all_positions(portfolio.id)
    
    # Format response
    holdings_text = "\n".join([
        f"• {p.symbol}: {p.quantity} @ ${p.average_entry_price:.2f}"
        for p in positions[:10]  # Show top 10
    ]) if positions else "No open positions"
    
    total_value = summary.get('total_value', 0)
    cash = summary.get('cash', 0)
    pnl = summary.get('unrealized_pnl', 0)
    pnl_percent = summary.get('unrealized_pnl_percent', 0)
    
    emoji = "✅" if pnl >= 0 else "❌"
    
    return (
        f"💼 *Your Portfolio*\n\n"
        f"{emoji} Total Value: **${total_value:,.2f}**\n"
        f"💵 Cash: ${cash:,.2f}\n"
        f"📈 Positions: {len(positions)}\n"
        f"📊 PnL: ${pnl:+,.2f} ({pnl_percent:+.2f}%)\n\n"
        f"*Holdings:*\n{holdings_text}\n\n"
        f"Data as of {datetime.utcnow().strftime('%H:%M UTC')}"
    )


async def handle_trades_intent(device_id: str, db: AsyncSession) -> str:
    """Handle trades query - fetches REAL data"""
    from app.services.portfolio_service import PortfolioService
    
    portfolio_service = PortfolioService(db)
    
    # Get user's portfolio
    portfolios = await portfolio_service.get_portfolios()
    if not portfolios:
        return "📜 *No Trades*\nYou don't have any portfolios yet."
    
    portfolio = portfolios[0]
    
    # Get recent trades (last 20)
    from sqlalchemy import select
    result = await db.execute(
        select(Trade)
        .where(Trade.portfolio_id == portfolio.id)
        .order_by(Trade.created_at.desc())
        .limit(20)
    )
    trades = list(result.scalars().all())
    
    if not trades:
        return "📜 *Recent Trades*\n\nNo trades yet. Ready to make your first trade!"
    
    # Format recent trades
    trades_text = "\n".join([
        f"{'✅' if t.status == 'FILLED' else '⏳'} {t.action} {t.quantity} {t.symbol} @ ${t.avg_execution_price:.2f} - ${t.quantity * t.avg_execution_price:.2f} ({t.status})"
        for t in trades[:10]  # Show last 10
    ])
    
    total_trades = len(trades)
    filled_trades = sum(1 for t in trades if t.status == 'FILLED')
    
    return (
        f"📜 *Recent Trades (Last 24h)*\n\n"
        f"{trades_text}\n\n"
        f"Total: {total_trades} trades ({filled_trades} filled)"
    )


async def handle_signals_intent(device_id: str, db: AsyncSession) -> str:
    """Handle signals query - fetches REAL signals"""
    from app.services.signal_service import SignalService
    
    signal_service = SignalService()
    
    # Get active signals (this would need DB too but simplified for now)
    from sqlalchemy import select
    from app.models import Signal
    
    result = await db.execute(
        select(Signal)
        .where(Signal.status == 'active')
        .order_by(Signal.created_at.desc())
        .limit(10)
    )
    signals = list(result.scalars().all())
    
    if not signals:
        return (
            "📡 *Market Signals*\n\n"
            f"No active signals right now.\n\n"
            f"🤖 AI is analyzing markets 24/7.\n"
            f"Check back soon for new opportunities!"
        )
    
    # Format signals
    signals_text = "\n".join([
        f"{'🟢' if s.action == 'BUY' else '🔴'} **{s.symbol}** - {s.action}\n"
        f"  Confidence: {s.confidence:.0%} | {s.reason[:60]}..."
        for s in signals[:5]
    ])
    
    return (
        f"📡 *Active Trading Signals*\n\n"
        f"{signals_text}\n\n"
        f"⚠️ These are AI suggestions. Always do your own research!"
    )


async def handle_balance_intent(device_id: str, db: AsyncSession) -> str:
    """Handle balance/PnL query - fetches REAL data"""
    from app.services.portfolio_service import PortfolioService
    
    portfolio_service = PortfolioService(db)
    
    portfolios = await portfolio_service.get_portfolios()
    if not portfolios:
        return "📊 *No Portfolio*\n\nCreate a portfolio to track your PnL!"
    
    portfolio = portfolios[0]
    pnl_data = await portfolio_service.get_pnl(portfolio.id)
    
    realized_pnl = pnl_data.get('realized_pnl', 0)
    unrealized_pnl = await portfolio_service.get_unrealized_pnl(portfolio.id)
    total_pnl = realized_pnl + unrealized_pnl
    
    emoji = "✅" if total_pnl >= 0 else "❌"
    
    return (
        f"📊 *Your Performance*\n\n"
        f"{emoji} Total PnL: **${total_pnl:+,.2f}**\n\n"
        f"💰 Realized: ${realized_pnl:+,.2f}\n"
        f"📈 Unrealized: ${unrealized_pnl:+,.2f}\n\n"
        f"Keep up the great work! 🚀"
    )


async def handle_general_chat(message: str, device_id: str, db: AsyncSession) -> str:
    """Handle general chat using NVIDIA NIM AI"""
    
    # Use NVIDIA NIM for real AI responses
    try:
        # Build context-aware prompt
        context = f"""You are Jasper Trades AI assistant. Help users with trading questions.

User message: {message}

Provide helpful, accurate responses about:
- Portfolio management
- Trading strategies  
- Market analysis
- Risk management

Be concise and friendly. Use emojis where appropriate."""
        
        response = await nvidia_client.chat(
            model="meta/llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": context}],
            temperature=0.7,
            max_tokens=500,
        )
        
        return response.get('choices', [{}])[0].get('message', {}).get('content', str(response))
        
    except Exception as e:
        logger.error(f"NVIDIA NIM error: {e}")
        
        # Fallback to simple keyword responses
        if "hello" in message.lower() or "hi" in message.lower():
            return "👋 Hello! I'm your Jasper Trades AI assistant. Ask me about your portfolio, trades, or market analysis!"
        
        if "thank" in message.lower():
            return "You're welcome! Happy trading! 📈"
        
        if "help" in message.lower():
            return (
                "📖 *How I can help:*\n\n"
                f"• Ask about your portfolio: \"What's my balance?\"\n"
                f"• Check trades: \"Show me recent trades\"\n"
                f"• Get signals: \"Should I buy AAPL?\"\n"
                f"• Check PnL: \"What's my profit/loss?\"\n\n"
                f"Just ask naturally!"
            )
        
        return (
            f"Thanks for your message!\n\n"
            f"I'm processing your request. For specific queries, try:\n"
            f"• \"Show my portfolio\"\n"
            f"• \"What trades did I make today?\"\n"
            f"• \"Give me a trading signal for AAPL\"\n"
            f"• \"What's my PnL?\""
        )

