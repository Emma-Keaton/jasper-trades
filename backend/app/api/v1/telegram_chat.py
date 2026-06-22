"""
Telegram Chat API
AI-powered chat responses for Telegram users
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from datetime import datetime

from app.database import get_db
from app.models import TelegramUser, ChatMessage
from app.services.telegram_bot_service import telegram_bot_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat/telegram", tags=["Telegram Chat"])


class TelegramChatRequest(BaseModel):
    """Telegram chat message"""
    chat_id: str
    message: str
    username: str


class TelegramChatResponse(BaseModel):
    """Telegram chat response"""
    response: str
    intent: str | None = None


@router.post("/", response_model=TelegramChatResponse)
async def telegram_chat(
    request: TelegramChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Process AI chat message from Telegram user.
    Detects intent and routes to appropriate handler.
    """
    try:
        # Find user by chat_id
        result = await db.execute(
            select(TelegramUser).where(TelegramUser.chat_id == request.chat_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_verified:
            raise HTTPException(status_code=404, detail="User not verified")

        # Store incoming message
        chat_message = ChatMessage(
            phone_number=request.chat_id,
            message=request.message,
            direction="incoming",
            message_type="text",
            intent=None,
        )
        db.add(chat_message)
        await db.flush()

        # Detect intent
        intent = detect_intent(request.message)
        chat_message.intent = intent
        logger.info(f"Telegram message intent: {intent}")

        # Route to handler based on intent
        if intent == "portfolio":
            response_text = await handle_portfolio_intent(user.device_id)
        elif intent == "trades":
            response_text = await handle_trades_intent(user.device_id)
        elif intent == "status":
            response_text = await handle_status_intent(user.device_id)
        elif intent == "signal":
            response_text = await handle_signal_intent(request.message, user.device_id)
        else:
            # General AI chat
            response_text = await handle_general_chat(request.message, user.device_id)

        # Store AI response
        ai_response = ChatMessage(
            phone_number=request.chat_id,
            message=response_text,
            direction="outgoing",
            message_type="ai_response",
            intent=intent,
            response_to_id=chat_message.id,
        )
        db.add(ai_response)
        await db.commit()

        # Update user last active
        user.last_active_at = datetime.utcnow()
        await db.commit()

        return TelegramChatResponse(
            response=response_text,
            intent=intent,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Telegram chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def detect_intent(message: str) -> str:
    """
    Simple intent detection based on keywords.
    For production, use NLP or fine-tuned model.
    """
    message_lower = message.lower()

    # Portfolio-related
    if any(word in message_lower for word in ["portfolio", "balance", "holdings", "positions", "value"]):
        return "portfolio"

    # Trades-related
    if any(word in message_lower for word in ["trade", "bought", "sold", "history", "recent"]):
        return "trades"

    # Status/account
    if any(word in message_lower for word in ["status", "account", "verified", "settings"]):
        return "status"

    # Trading signals
    if any(word in message_lower for word in ["signal", "buy", "sell", "recommendation", "should i"]):
        return "signal"

    # Default: general chat
    return "general"


async def handle_portfolio_intent(device_id: str) -> str:
    """Handle portfolio query"""
    # TODO: Fetch real portfolio data from backend
    return (
        "💼 *Your Portfolio*\n\n"
        f"Total Value: $100,000.00\n"
        f"Cash: $50,000.00\n"
        f"Positions: 5\n"
        f"PnL: +$5,000.00 (+5.00%)\n\n"
        f"📈 *Top Holdings:*\n"
        f"• AAPL: 100 @ $150.00 (+$2,500.00)\n"
        f"• MSFT: 50 @ $320.00 (+$1,200.00)\n"
        f"• GOOGL: 20 @ $140.00 (+$300.00)\n\n"
        f"Data as of {datetime.utcnow().strftime('%H:%M UTC')}"
    )


async def handle_trades_intent(device_id: str) -> str:
    """Handle trades query"""
    # TODO: Fetch real trade history
    return (
        "📜 *Recent Trades (Last 24h)*\n\n"
        f"✅ BUY 100 AAPL @ $150.00 - $15,000.00\n"
        f"✅ SELL 50 MSFT @ $320.00 - +$2,500.00\n"
        f"✅ BUY 20 GOOGL @ $140.00 - $2,800.00\n\n"
        f"Total: 3 trades, +$2,500.00 PnL"
    )


async def handle_status_intent(device_id: str) -> str:
    """Handle status query"""
    # TODO: Fetch real account status
    return (
        "📊 *Account Status*\n\n"
        f"✅ Telegram notifications enabled\n"
        f"✅ Daily summary scheduled for 8 PM WAT\n"
        f"✅ AI chat active\n\n"
        f"Ready to trade!"
    )


async def handle_signal_intent(message: str, device_id: str) -> str:
    """Handle trading signal request"""
    # TODO: Call AI model to generate signal
    return (
        "📡 *Market Analysis*\n\n"
        f"Based on current market conditions:\n\n"
        f"• AAPL: 🟢 Bullish (70% confidence)\n"
        f"  - Breaking resistance at $150\n"
        f"  - Volume surge detected\n\n"
        f"• MSFT: 🔴 Bearish (60% confidence)\n"
        f"  - Resistance at $325\n"
        f"  - Consider taking profits\n\n"
        f"⚠️ This is not financial advice. Trade at your own risk."
    )


async def handle_general_chat(message: str, device_id: str) -> str:
    """Handle general AI chat"""
    # TODO: Integrate with NVIDIA NIM for AI responses
    
    # Simple keyword-based responses for now
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
            f"• Account status: \"Am I verified?\"\n\n"
            f"Just ask naturally!"
        )

    # Default AI response
    return (
        f"Thanks for your message: \"{message}\"\n\n"
        f"I'm processing your request. For specific queries, try:\n"
        f"• \"Show my portfolio\"\n"
        f"• \"What trades did I make today?\"\n"
        f"• \"Give me a trading signal for AAPL\""
    )