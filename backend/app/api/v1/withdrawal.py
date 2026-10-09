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
# Use the centralized encryption service (SECRET_KEY-derived key) so secrets
# are always encrypted at rest with a stable, non-committed key.

from app.services.encryption import EncryptionHelper
from app.services import payout_rail

encryption = EncryptionHelper()


# ============ Request Models ============

class WithdrawalRequest(BaseModel):
    """Manual withdrawal request"""
    amount: float = Field(..., gt=0, description="Amount to withdraw")
    destination_type: str = Field(..., description="crypto_wallet or broker")
    destination_address: Optional[str] = None
    destination_chain: Optional[str] = Field(
        default=None,
        description=(
            "Network for a crypto withdrawal: tron | bsc | polygon | ethereum | "
            "solana. Required when destination_type is crypto_wallet."
        ),
    )


class PayoutWalletKeysRequest(BaseModel):
    """Payout hot-wallet signing keys, one per chain family.

    `evm` covers Ethereum, BSC and Polygon (one key, one address). Tron and Solana
    are separate keyspaces and need their own keys. Leave a family out if you
    will not receive payouts on it.
    """

    evm: Optional[str] = Field(
        default=None, description="0x-prefixed EVM private key (32 bytes)"
    )
    tron: Optional[str] = Field(
        default=None, description="Tron private key, 64 hex characters, no 0x"
    )
    solana: Optional[str] = Field(
        default=None, description="Solana secret key, base58"
    )


class PayoutSettingsRequest(BaseModel):
    """Payout settings configuration"""
    crypto_wallet: Optional[str] = None
    payout_enabled: bool = False
    payout_percentage: float = Field(default=50.0, ge=0, le=100)
    payout_schedule_hour: int = Field(default=20, ge=0, le=23)
    payout_schedule_minute: int = Field(default=0, ge=0, le=59)
    payout_frequency: str = Field(default="custom_time", pattern="^(custom_time|end_of_trade)$")
    min_payout_threshold: float = Field(default=10.0, ge=0)
    broker_account: Optional[str] = None
    payout_chain: str = Field(
        default="tron",
        description=(
            "Network the crypto payout is sent on: tron | bsc | polygon | "
            "ethereum | solana. Tron is the practical default for Nigerian users "
            "because Nigerian off-ramps are TRC20."
        ),
    )


class ValidateWalletRequest(BaseModel):
    """Crypto wallet validation request"""
    address: str
    network: str = "tron"


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

        if request.destination_type == "crypto_wallet":
            # A crypto withdrawal must name its network. Without this the
            # transfer could not be signed at all, so fail at request time with
            # a clear message instead of at send time.
            try:
                payout_rail.get_chain(request.destination_chain or "")
            except payout_rail.PayoutRailError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        withdrawal_service = get_withdrawal_service(db)
        withdrawal = await withdrawal_service.create_withdrawal(
            portfolio_id=portfolio_id,
            amount=request.amount,
            withdrawal_type="manual",
            destination_type=request.destination_type,
            destination_address=request.destination_address or "",
            destination_chain=request.destination_chain,
        )

        return {
            "success": True,
            "withdrawal_id": withdrawal.id,
            "amount": withdrawal.amount,
            "fee": withdrawal.fee,
            "net_amount": withdrawal.net_amount,
            "status": withdrawal.status,
            "destination_chain": withdrawal.destination_chain,
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

    try:
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
                "payout_schedule_minute": 0,
                "payout_frequency": "custom_time",
                "min_payout_threshold": 10.0,
                "payout_chain": "tron",
                "payout_keys_configured": _key_families(settings),
                "supported_chains": payout_rail.describe_chains(),
            }

        encryption = EncryptionHelper()
        payout_config = encryption.decrypt_json(settings.payout_config)

        return {
            "configured": True,
            "crypto_wallet": payout_config.get("crypto_wallet", ""),
            "payout_enabled": payout_config.get("payout_enabled", False),
            "payout_percentage": payout_config.get("payout_percentage", 50.0),
            "payout_schedule_hour": payout_config.get("payout_schedule_hour", 20),
            "payout_schedule_minute": payout_config.get("payout_schedule_minute", 0),
            "payout_frequency": payout_config.get("payout_frequency", "custom_time"),
            "min_payout_threshold": payout_config.get("min_payout_threshold", 10.0),
            "payout_chain": payout_config.get("payout_chain", "tron"),
            # Which key families exist, never the keys themselves.
            "payout_keys_configured": _key_families(settings),
            "supported_chains": payout_rail.describe_chains(),
        }
    except Exception as e:
        logger.error(f"Error fetching payout settings: {e}")
        return {
            "configured": False,
            "payout_enabled": False,
            "payout_percentage": 50.0,
            "payout_schedule_hour": 20,
            "payout_schedule_minute": 0,
            "payout_frequency": "custom_time",
            "min_payout_threshold": 10.0,
            "payout_chain": "tron",
            "error": "Failed to load settings",
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

    # Validate the chain and address together, before saving. Catching a mismatch
    # here means the operator finds out now, not at 8 PM when the payout fires.
    if settings_req.crypto_wallet:
        try:
            chain = payout_rail.get_chain(settings_req.payout_chain)
            payout_rail.validate_address(chain.id, settings_req.crypto_wallet)
        except payout_rail.PayoutRailError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    payout_config = {
        "crypto_wallet": settings_req.crypto_wallet,
        "payout_enabled": settings_req.payout_enabled,
        "payout_percentage": settings_req.payout_percentage,
        "payout_schedule_hour": settings_req.payout_schedule_hour,
        "payout_schedule_minute": settings_req.payout_schedule_minute,
        "payout_frequency": settings_req.payout_frequency,
        "min_payout_threshold": settings_req.min_payout_threshold,
        "broker_account": settings_req.broker_account,
        "payout_chain": settings_req.payout_chain,
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

    logger.info(
        f"Payout settings saved for device {device_id} "
        f"(chain={settings_req.payout_chain})"
    )

    return {
        "success": True,
        "payout_enabled": settings_req.payout_enabled,
        "payout_percentage": settings_req.payout_percentage,
        "payout_schedule_hour": settings_req.payout_schedule_hour,
        "payout_schedule_minute": settings_req.payout_schedule_minute,
        "payout_frequency": settings_req.payout_frequency,
        "min_payout_threshold": settings_req.min_payout_threshold,
        "payout_chain": settings_req.payout_chain,
        "supported_chains": payout_rail.describe_chains(),
    }


@router.get("/payout/chains")
async def list_payout_chains():
    """List supported payout networks with their approximate costs.

    Read-only and unauthenticated: it exposes no user data, and the frontend
    needs it to render the network picker.
    """
    return {"chains": payout_rail.describe_chains()}


@router.post("/payout/keys")
async def save_payout_keys(
    keys_req: PayoutWalletKeysRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Store the payout hot-wallet signing keys, encrypted.

    One key per chain family. `evm` covers Ethereum, BSC and Polygon together.
    Keys are never returned by any endpoint - only which families are configured.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    bundle = {
        "evm": keys_req.evm,
        "tron": keys_req.tron,
        "solana": keys_req.solana,
    }
    if not any(bundle.values()):
        raise HTTPException(
            status_code=400, detail="At least one chain-family key is required"
        )

    # Reject malformed keys now. Deferring this to payout time would fail at the
    # moment money was meant to move.
    if bundle["evm"]:
        _guard_key(bundle["evm"], "EVM", lambda k: len(k) == 64 and all(
            c in "0123456789abcdefABCDEF" for c in k
        ))
    if bundle["tron"]:
        _guard_key(bundle["tron"], "Tron", lambda k: len(k) == 64 and all(
            c in "0123456789abcdefABCDEF" for c in k
        ))
    if bundle["solana"]:
        # base58, no 0/0/O/I/l
        base58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        _guard_key(
            bundle["solana"], "Solana",
            lambda k: 32 <= len(k) <= 90 and set(k) <= base58,
        )

    encrypted = encryption.encrypt_json(bundle)

    async with db as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        device_settings = result.scalar_one_or_none()
        if device_settings:
            device_settings.payout_wallet_keys = encrypted
        else:
            session.add(
                DeviceSettings(device_id=device_id, payout_wallet_keys=encrypted)
            )
        await session.commit()

    # Names only. Never log or return key material.
    logger.info(
        "Payout keys saved for device %s (families: %s)",
        device_id,
        ", ".join(sorted(k for k, v in bundle.items() if v)),
    )
    return {
        "success": True,
        "payout_keys_configured": sorted(k for k, v in bundle.items() if v),
    }


def _guard_key(key: str, label: str, predicate) -> None:
    """Raise a 400 if a stored key is malformed, without echoing it back.

    The error deliberately omits the key: it travels to the client in the
    response and into logs via the request pipeline.
    """
    body = key[2:] if label == "EVM" and key.startswith("0x") else key
    if not predicate(body):
        raise HTTPException(
            status_code=400,
            detail=f"{label} payout key is malformed; check the format",
        )


def _key_families(settings) -> list:
    """Which payout key families are configured, without decrypting them.

    Deliberately does not decrypt: this endpoint is read by the settings UI on
    load, and there is no reason to pull private keys into memory to render a
    checklist. It reports presence by inspecting the encrypted blob's shape.
    """
    if settings is None or not getattr(settings, "payout_wallet_keys", None):
        return []
    try:
        bundle = encryption.decrypt_json(settings.payout_wallet_keys) or {}
    except Exception:  # noqa: BLE001
        logger.warning("Could not read payout key bundle for settings page")
        return []
    return sorted(k for k, v in bundle.items() if v)


@router.post("/payout/validate-wallet")
async def validate_crypto_wallet(request: ValidateWalletRequest):
    """Validate a payout address against the rules for one network.

    Delegates to `payout_rail` so validation here and validation at send time
    cannot disagree. The previous inline regexes accepted only Ethereum and
    Solana, which meant a valid Tron address - the practical default for
    Nigerian users - was reported as an "unsupported network".
    """
    try:
        chain = payout_rail.get_chain(request.network)
    except payout_rail.PayoutRailError as exc:
        return {"valid": False, "message": str(exc)}

    try:
        address = payout_rail.validate_address(chain.id, request.address)
    except payout_rail.PayoutRailError as exc:
        return {"valid": False, "message": str(exc)}

    return {
        "valid": True,
        "network": chain.id,
        "network_label": chain.label,
        "address": address[:10] + "..." + address[-5:],
    }