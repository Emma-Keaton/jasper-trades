"""
Exness API Endpoints

Endpoints for Exness/MT5 broker integration:
- Account linking (MT5 login, server, password)
- Account sync (balance, equity, positions)
- Trading operations (buy, sell, close)
- Withdrawal requests
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog
from datetime import datetime

from app.database import get_db, async_session
from app.models import BrokerAccount, Portfolio, DeviceSettings
from app.services.encryption import EncryptionHelper

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/exness", tags=["exness"])


# ============ Request Models ============

class LinkExnessAccountRequest(BaseModel):
    """Link Exness MT5 account request."""
    portfolio_id: int
    login_id: str = Field(..., description="MT5 Login ID (e.g., 87291043)")
    server: str = Field(..., description="MT5 Server (e.g., Exness-MT5-Real6)")
    password: str = Field(..., description="Trading password")
    investor_password: Optional[str] = Field(None, description="Investor password (read-only)")
    broker_name: Optional[str] = Field("Exness", description="Display name")


class ExnessTradeRequest(BaseModel):
    """Exness trade execution request."""
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    type: str = Field(..., description="buy or sell")
    volume: float = Field(..., gt=0, description="Lot size")
    sl: Optional[float] = Field(None, description="Stop loss price")
    tp: Optional[float] = Field(None, description="Take profit price")
    comment: Optional[str] = Field("Jasper Trades", description="Order comment")


class ExnessWithdrawalRequest(BaseModel):
    """Exness withdrawal request."""
    portfolio_id: int
    amount: float = Field(..., gt=0, description="Withdrawal amount")
    destination_address: Optional[str] = Field(None, description="External wallet address")


# ============ Helper Functions ============

def get_encryption_helper() -> EncryptionHelper:
    return EncryptionHelper()


# ============ Account Linking Endpoints ============

@router.post("/account/link")
async def link_exness_account(
    request: LinkExnessAccountRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Link Exness MT5 account to Jasper Trades.
    
    Credentials are encrypted before storage.
    Supports both local (MT5) and cloud (REST API) hosting.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    encryption = get_encryption_helper()
    
    try:
        # Also save to DeviceSettings for global access
        result = await db.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        settings = result.scalar_one_or_none()
        
        if settings:
            settings.exness_login_id = request.login_id
            settings.exness_server = request.server
            settings.exness_password = encryption.encrypt(request.password)
            if request.investor_password:
                settings.exness_investor_password = encryption.encrypt(request.investor_password)
            settings.exness_enabled = True
        else:
            settings = DeviceSettings(
                device_id=device_id,
                exness_login_id=request.login_id,
                exness_server=request.server,
                exness_password=encryption.encrypt(request.password),
                exness_investor_password=encryption.encrypt(request.investor_password) if request.investor_password else None,
                exness_enabled=True,
            )
            db.add(settings)
        
        # Create broker account record
        broker_account = BrokerAccount(
            portfolio_id=request.portfolio_id,
            broker_type="exness",
            broker_name=request.broker_name or f"Exness {request.login_id}",
            account_id=request.login_id,
            account_password=encryption.encrypt(request.password),
            investor_password=encryption.encrypt(request.investor_password) if request.investor_password else None,
            server_name=request.server,
            is_connected=False,  # Will be set on first sync
            currency="USD",
        )
        db.add(broker_account)
        
        await db.commit()
        
        logger.info(f"Exness account linked: {request.login_id} @ {request.server}")
        
        return {
            "success": True,
            "account_id": request.login_id,
            "server": request.server,
            "broker_name": request.broker_name or "Exness",
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Link Exness account failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to link account: {str(e)}")


@router.get("/account/status")
async def get_exness_account_status(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get Exness account connection status and info."""
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.portfolio_id == portfolio_id,
            BrokerAccount.broker_type == "exness"
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        # Check DeviceSettings
        device_result = await db.execute(select(DeviceSettings).limit(1))
        settings = device_result.scalar_one_or_none()
        
        if settings and settings.exness_login_id:
            return {
                "linked": False,
                "configured": True,
                "login_id": settings.exness_login_id,
                "server": settings.exness_server,
                "enabled": settings.exness_enabled,
                "message": "Exness configured in settings but not linked to portfolio",
            }
        
        return {"linked": False, "configured": False}
    
    return {
        "linked": True,
        "account_id": account.account_id,
        "broker_name": account.broker_name,
        "server": account.server_name,
        "is_connected": account.is_connected,
        "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "balance": account.balance,
        "equity": account.equity,
        "margin": account.margin,
        "free_margin": account.free_margin,
        "currency": account.currency,
    }


@router.post("/account/sync")
async def sync_exness_account(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync Exness account data (balance, equity, positions).
    
    Tries MT5 first (local Windows), falls back to REST API (cloud).
    """
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.portfolio_id == portfolio_id,
            BrokerAccount.broker_type == "exness"
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Exness account not linked")
    
    # Try MT5 first (local Windows)
    mt5_success = False
    try:
        from app.services.mt5_service import get_mt5_service, is_mt5_available
        
        if is_mt5_available():
            mt5 = get_mt5_service()
            
            # Get credentials
            encryption = get_encryption_helper()
            password = encryption.decrypt(account.account_password) if account.account_password else None
            
            # Connect if not already connected
            if not mt5.is_connected():
                import asyncio
                connected = await asyncio.to_thread(
                    mt5.connect,
                    int(account.account_id),
                    account.server_name,
                    password
                )
            
            if mt5.is_connected():
                # Get account info
                import asyncio
                info = await asyncio.to_thread(mt5.get_account_info)
                
                if info:
                    account.balance = info.get("balance", 0.0)
                    account.equity = info.get("equity", 0.0)
                    account.margin = info.get("margin", 0.0)
                    account.free_margin = info.get("free_margin", 0.0)
                    account.is_connected = True
                    account.last_sync_at = datetime.utcnow()
                    account.connection_error = None
                    
                    await db.commit()
                    mt5_success = True
                    
                    logger.info(f"Exness account synced via MT5: ${info.get('balance')}")
                    
    except Exception as e:
        logger.warning(f"MT5 sync failed, trying REST API: {e}")
    
    # Fall back to REST API
    if not mt5_success:
        try:
            from app.services.exness_service import get_exness_service
            
            # Get API credentials from settings
            device_result = await db.execute(select(DeviceSettings).limit(1))
            settings = device_result.scalar_one_or_none()
            
            if not settings:
                raise HTTPException(status_code=400, detail="Exness API credentials not configured")
            
            # Note: Exness REST API requires separate API key/secret (not MT5 credentials)
            # For now, return cached data
            account.is_connected = False
            account.connection_error = "REST API requires Exness API key/secret"
            await db.commit()
            
        except Exception as e:
            logger.error(f"REST API sync failed: {e}")
            account.is_connected = False
            account.connection_error = str(e)
            await db.commit()
    
    # Refresh account
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == account.id)
    )
    account = result.scalar_one()
    
    return {
        "success": True,
        "balance": account.balance,
        "equity": account.equity,
        "margin": account.margin,
        "free_margin": account.free_margin,
        "is_connected": account.is_connected,
    }


@router.get("/positions")
async def get_exness_positions(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get all open Exness positions."""
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.portfolio_id == portfolio_id,
            BrokerAccount.broker_type == "exness"
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Exness account not linked")
    
    # Try MT5
    positions = []
    try:
        from app.services.mt5_service import get_mt5_service, is_mt5_available
        
        if is_mt5_available():
            mt5 = get_mt5_service()
            if mt5.is_connected():
                import asyncio
                positions = await asyncio.to_thread(mt5.get_positions)
                
    except Exception as e:
        logger.error(f"Get positions failed: {e}")
    
    return {"positions": positions, "count": len(positions)}


@router.get("/symbols")
async def get_exness_symbols(
    db: AsyncSession = Depends(get_db),
):
    """Get list of available Exness trading symbols."""
    symbols = []
    
    # Try MT5
    try:
        from app.services.mt5_service import get_mt5_service, is_mt5_available
        
        if is_mt5_available():
            mt5 = get_mt5_service()
            symbols = await mt5.get_symbols()
            
    except Exception as e:
        logger.error(f"Get symbols failed: {e}")
    
    # If MT5 failed, try REST API
    if not symbols:
        try:
            from app.services.exness_service import get_exness_service
            
            exness = get_exness_service()
            import asyncio
            symbols = await asyncio.to_thread(exness.get_symbols)
            
        except Exception as e:
            logger.error(f"REST API symbols failed: {e}")
    
    return {"symbols": symbols, "count": len(symbols)}


# ============ Trading Endpoints ============

@router.post("/trade")
async def execute_exness_trade(
    request: ExnessTradeRequest,
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Execute trade on Exness via MT5 or REST API."""
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.portfolio_id == portfolio_id,
            BrokerAccount.broker_type == "exness"
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Exness account not linked")
    
    # Validate trading caps
    caps_result = await db.execute(
        select(BrokerAccount.portfolio_id)  # We need to query TradingCap separately
    )
    # TODO: Add trading cap validation here
    
    # Execute via MT5 or REST API
    result = None
    try:
        from app.services.mt5_service import get_mt5_service, is_mt5_available
        
        if is_mt5_available():
            mt5 = get_mt5_service()
            import asyncio
            
            if request.type.lower() == "buy":
                result = await asyncio.to_thread(
                    mt5.market_buy,
                    request.symbol,
                    request.volume,
                    request.sl,
                    request.tp,
                    request.comment
                )
            else:
                result = await asyncio.to_thread(
                    mt5.market_sell,
                    request.symbol,
                    request.volume,
                    request.sl,
                    request.tp,
                    request.comment
                )
                
    except Exception as e:
        logger.error(f"MT5 trade failed: {e}")
    
    if not result or not result.get("success"):
        # Try REST API
        try:
            from app.services.exness_service import get_exness_service
            
            exness = get_exness_service()
            import asyncio
            
            if request.type.lower() == "buy":
                result = await asyncio.to_thread(
                    exness.buy,
                    request.symbol,
                    request.volume,
                    request.sl,
                    request.tp,
                    request.comment
                )
            else:
                result = await asyncio.to_thread(
                    exness.sell,
                    request.symbol,
                    request.volume,
                    request.sl,
                    request.tp,
                    request.comment
                )
                
        except Exception as e:
            logger.error(f"REST API trade failed: {e}")
            raise HTTPException(status_code=500, detail=f"Trade execution failed: {e}")
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Trade failed"))
    
    return {
        "success": True,
        "ticket": result.get("ticket") or result.get("id"),
        "symbol": request.symbol,
        "type": request.type,
        "volume": request.volume,
        "price": result.get("price"),
    }


@router.post("/position/close/{position_id}")
async def close_exness_position(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Close an open Exness position."""
    try:
        from app.services.mt5_service import get_mt5_service, is_mt5_available
        
        if is_mt5_available():
            mt5 = get_mt5_service()
            import asyncio
            
            result = await asyncio.to_thread(mt5.close_position, position_id)
            
            if result and result.get("success"):
                return {"success": True, "deal": result.get("deal")}
            else:
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to close"))
        
        # Try REST API
        from app.services.exness_service import get_exness_service
        exness = get_exness_service()
        import asyncio
        
        result = await asyncio.to_thread(exness.close_position, str(position_id))
        
        if result and result.get("success"):
            return {"success": True}
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to close"))
            
    except Exception as e:
        logger.error(f"Close position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Withdrawal Endpoints ============

@router.post("/withdraw")
async def request_exness_withdrawal(
    request: ExnessWithdrawalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request withdrawal to Exness account.
    
    Note: This is for withdrawing FROM Jasper TO Exness.
    For withdrawing FROM Exness to external wallet, use Exness directly.
    """
    from app.services.withdrawal_service import get_withdrawal_service
    
    withdrawal_service = get_withdrawal_service(db)
    
    try:
        withdrawal = await withdrawal_service.create_withdrawal(
            portfolio_id=request.portfolio_id,
            amount=request.amount,
            withdrawal_type="manual",
            destination_type="exness",
            destination_address=request.destination_address or "",
        )
        
        return {
            "success": True,
            "withdrawal_id": withdrawal.id,
            "amount": withdrawal.amount,
            "fee": withdrawal.fee,
            "net_amount": withdrawal.net_amount,
            "status": withdrawal.status,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Exness withdrawal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))