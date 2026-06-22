"""
Telegram Bot Data API
Endpoints specifically for Telegram bot to fetch user-specific data
Maps chat_id → device_id internally
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import structlog

from app.database import get_db
from app.models import TelegramUser, Trade, Position, DeviceSettings
from datetime import datetime

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telegram/data", tags=["Telegram Bot Data"])


async def get_device_id_from_chat_id(db: AsyncSession, chat_id: str) -> Optional[str]:
    """Helper to resolve chat_id to device_id"""
    result = await db.execute(
        select(TelegramUser).where(
            TelegramUser.chat_id == str(chat_id),
            TelegramUser.is_verified == True
        )
    )
    user = result.scalar_one_or_none()
    return user.device_id if user else None


@router.get("/portfolio")
async def get_portfolio_for_telegram(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get portfolio for Telegram user.
    Resolves chat_id → device_id → portfolio
    """
    device_id = await get_device_id_from_chat_id(db, chat_id)
    
    if not device_id:
        raise HTTPException(status_code=404, detail="Chat ID not verified. Please verify in the app first.")
    
    # Get trading accounts for this device
    from app.models import TradingAccount
    result = await db.execute(
        select(TradingAccount).where(
            TradingAccount.device_id == device_id,
            TradingAccount.is_connected == True
        )
    )
    accounts = result.scalars().all()
    
    if not accounts:
        return {
            "portfolio": None,
            "message": "No trading accounts connected"
        }
    
    # Calculate portfolio summary
    total_balance = sum(acc.account_balance or 0 for acc in accounts)
    total_equity = sum(acc.account_equity or 0 for acc in accounts)
    
    # Get positions
    positions_result = await db.execute(
        select(Position).where(Position.device_id == device_id)
    )
    positions = positions_result.scalars().all()
    
    holdings = []
    for pos in positions:
        holdings.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "avg_price": pos.avg_price,
            "current_price": pos.current_price or 0,
            "market_value": pos.market_value or (pos.quantity * (pos.current_price or 0)),
            "unrealized_pnl": pos.unrealized_pnl or 0,
            "unrealized_pnl_percent": pos.unrealized_pnl_percent or 0,
        })
    
    total_pnl = sum(h["unrealized_pnl"] for h in holdings)
    pnl_percent = (total_pnl / total_equity * 100) if total_equity > 0 else 0
    
    return {
        "portfolio": {
            "total_value": total_equity,
            "cash": total_balance,
            "positions_count": len(holdings),
            "total_pnl": total_pnl,
            "pnl_percent": pnl_percent,
            "holdings": holdings,
        },
        "accounts": [
            {
                "broker": acc.broker_name,
                "balance": acc.account_balance,
                "equity": acc.account_equity,
            }
            for acc in accounts
        ]
    }


@router.get("/trades")
async def get_trades_for_telegram(
    chat_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent trades for Telegram user.
    Resolves chat_id → device_id → trades
    """
    device_id = await get_device_id_from_chat_id(db, chat_id)
    
    if not device_id:
        raise HTTPException(status_code=404, detail="Chat ID not verified. Please verify in the app first.")
    
    # Get trades for this device
    from sqlalchemy import desc
    result = await db.execute(
        select(Trade)
        .where(Trade.device_id == device_id)
        .order_by(desc(Trade.created_at))
        .limit(limit)
    )
    trades = result.scalars().all()
    
    if not trades:
        return {
            "trades": [],
            "message": "No trades found"
        }
    
    trade_list = []
    for trade in trades:
        trade_list.append({
            "id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "total": trade.quantity * (trade.price or 0),
            "agent": trade.agent_name or "AI",
            "status": trade.status,
            "created_at":trade.created_at.isoformat() if trade.created_at else None,
        })
    
    # Calculate summary
    total_trades = len(trades)
    buy_trades = [t for t in trades if t.side == "buy"]
    sell_trades = [t for t in trades if t.side == "sell"]
    
    return {
        "trades": trade_list,
        "summary": {
            "total": total_trades,
            "buys": len(buy_trades),
            "sells": len(sell_trades),
            "last_24h": sum(1 for t in trades if t.created_at and (datetime.utcnow() - t.created_at).total_seconds() < 86400)
        }
    }


@router.get("/status")
async def get_status_for_telegram(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get account status for Telegram user.
    """
    device_id = await get_device_id_from_chat_id(db, chat_id)
    
    if not device_id:
        return {
            "is_verified": False,
            "chat_id": chat_id,
            "message": "Chat ID not verified"
        }
    
    # Get settings
    settings_result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    settings = settings_result.scalar_one_or_none()
    
    telegram_config = settings.telegram_config if settings else {}
    
    return {
        "is_verified": True,
        "chat_id": chat_id,
        "device_id": device_id[:8] + "***",
        "preferences": {
            "trade_notifications_enabled": telegram_config.get("trade_notifications_enabled", False),
            "daily_summary_enabled": telegram_config.get("daily_summary_enabled", False),
            "chat_enabled": telegram_config.get("chat_enabled", False),
            "ai_explanations_enabled": telegram_config.get("ai_explanations_enabled", False),
        }
    }