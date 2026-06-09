"""
Withdrawal API endpoints
Handle manual withdrawals and auto-payout configuration
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog
from datetime import datetime
import json
import os

from app.database import get_db, async_session
from app.models import Withdrawal, Portfolio, DeviceSettings
from app.services.withdrawal_service import WithdrawalService, get_withdrawal_service
from app.services.payout_scheduler import payout_scheduler, get_payout_scheduler

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/withdrawal", tags=["withdrawal"])


# ============ Encryption Helper ============

class EncryptionHelper:
    def __init__(self):
        self.key = None
        self.cipher = None
        try:
            from cryptography.fernet import Fernet
            key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "encryption.key")
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    self.key = f.read()
                    self.cipher = Fernet(self.key)
        except ImportError:
            pass
    
    def encrypt_json(self, data):
        if not self.cipher or not data:
            return json.dumps(data)
        json_str = json.dumps(data)
        return self.cipher.encrypt(json_str.encode()).decode()
    
    def decrypt_json(self, value):
        if not self.cipher or not value:
            return json.loads(value)
        try:
            decrypted = self.cipher.decrypt(value.encode()).decode()
            return json.loads(decrypted)
        except:
            return json.loads(value)

encryption = EncryptionHelper()


# ============ Request Models ============

class WithdrawalRequest(BaseModel):
    """Manual withdrawal request"""
    amount: float = Field(..., gt=0, description="Amount to withdraw")
    destination_type: str = Field(..., description="crypto_wallet or broker")
    destination_address: Optional[str] = None


class PayoutSettingsRequest(BaseModel):
    """Payout settings configuration"""
    crypto_wallet: Optional[str] = None
    payout_enabled: bool = False
    payout_percentage: float = Field(default=50.0, ge=0, le=100)
    payout_schedule_hour: int = Field(default=20, ge=0, le=23)
    broker_account: Optional[str] = None


class ValidateWalletRequest(BaseModel):
    """Crypto wallet validation request"""
    address: str
    network: str = "ethereum"


# ============ Withdrawal Endpoints ============

@router.post("/request")
async def request_withdrawal(
    request: WithdrawalRequest,
    portfolio_id: int = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """Request a manual withdrawal."""
    try:
        if request.destination_type not in ["crypto_wallet", "broker"]:
            raise HTTPException(status_code=400, detail="Invalid destination type")
        
        if request.destination_type == "crypto_wallet" and not request.destination_address:
            raise HTTPException(status_code=400, detail="Crypto wallet address required")
        
        withdrawal_service = get_withdrawal_service(db)
        withdrawal = await withdrawal_service.create_withdrawal(
            portfolio_id=portfolio_id,
            amount=request.amount,
            withdrawal_type="manual",
            destination_type=request.destination_type,
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
        logger.error(f"Withdrawal request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/{withdrawal_id}")
async def process_withdrawal(
    withdrawal_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Process a pending withdrawal request."""
    try:
        withdrawal_service = get_withdrawal_service(db)
        withdrawal = await withdrawal_service.process_withdrawal(withdrawal_id)
        
        return {
            "success": True,
            "withdrawal_id": withdrawal.id,
            "status": withdrawal.status,
            "transaction_hash": withdrawal.transaction_hash,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Withdrawal processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_withdrawal_history(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    limit: int = Query(default=50, ge=1, le=200),
    withdrawal_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get withdrawal history."""
    withdrawal_service = get_withdrawal_service(db)
    withdrawals = await withdrawal_service.get_withdrawal_history(
        portfolio_id=portfolio_id,
        limit=limit,
        withdrawal_type=withdrawal_type,
    )
    
    return {
        "withdrawals": [
            {
                "id": w.id,
                "amount": w.amount,
                "fee": w.fee,
                "net_amount": w.net_amount,
                "type": w.withdrawal_type,
                "status": w.status,
                "requested_at": w.requested_at.isoformat() if w.requested_at else None,
            }
            for w in withdrawals
        ],
        "count": len(withdrawals),
    }


@router.get("/stats")
async def get_withdrawal_stats(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get withdrawal statistics."""
    withdrawal_service = get_withdrawal_service(db)
    stats = await withdrawal_service.get_withdrawal_stats(portfolio_id)
    
    return {"stats": stats}


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get auto-payout scheduler status."""
    return {"scheduler": payout_scheduler.get_status()}


@router.post("/scheduler/execute/{portfolio_id}")
async def execute_immediate_payout(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Execute auto-payout immediately (for testing)."""
    try:
        scheduler = get_payout_scheduler()
        executed = await scheduler.execute_immediate_payout(portfolio_id)
        
        return {
            "success": executed,
            "message": "Auto-payout executed" if executed else "No payout executed",
        }
        
    except Exception as e:
        logger.error(f"Immediate payout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Payout Settings Endpoints ============

@router.get("/payout/settings")
async def get_payout_settings(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get payout configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        settings = result.scalar_one_or_none()
    
    if not settings or not settings.payout_config:
        return {
            "configured": False,
            "payout_enabled": False,
            "payout_percentage": 50.0,
            "payout_schedule_hour": 20,
        }
    
    payout_config = encryption.decrypt_json(settings.payout_config)
    
    return {
        "configured": True,
        "crypto_wallet": payout_config.get("crypto_wallet", ""),
        "payout_enabled": payout_config.get("payout_enabled", False),
        "payout_percentage": payout_config.get("payout_percentage", 50.0),
        "payout_schedule_hour": payout_config.get("payout_schedule_hour", 20),
    }


@router.post("/payout/settings")
async def save_payout_settings(
    settings_req: PayoutSettingsRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Save payout configuration."""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    payout_config = {
        "crypto_wallet": settings_req.crypto_wallet,
        "payout_enabled": settings_req.payout_enabled,
        "payout_percentage": settings_req.payout_percentage,
        "payout_schedule_hour": settings_req.payout_schedule_hour,
        "broker_account": settings_req.broker_account,
    }
    
    encrypted_config = encryption.encrypt_json(payout_config)
    
    async with db as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        device_settings = result.scalar_one_or_none()
        
        if device_settings:
            device_settings.payout_config = encrypted_config
        else:
            device_settings = DeviceSettings(
                device_id=device_id,
                payout_config=encrypted_config,
            )
            session.add(device_settings)
        
        await session.commit()
    
    logger.info(f"Payout settings saved for device {device_id}")
    
    return {
        "success": True,
        "payout_enabled": settings_req.payout_enabled,
        "payout_percentage": settings_req.payout_percentage,
        "payout_schedule_hour": settings_req.payout_schedule_hour,
    }


@router.post("/payout/validate-wallet")
async def validate_crypto_wallet(request: ValidateWalletRequest):
    """Validate crypto wallet address format."""
    import re
    address = request.address.strip()
    network = request.network.lower()
    
    if network in ["ethereum", "erc20"]:
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return {"valid": False, "message": "Invalid Ethereum address"}
    elif network in ["solana", "spl"]:
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
            return {"valid": False, "message": "Invalid Solana address"}
    else:
        return {"valid": False, "message": f"Unsupported network: {network}"}
    
    return {
        "valid": True,
        "network": network,
        "address": address[:10] + "..." + address[-5:],
    }