"""Crypto Connector API – per‑device storage of exchange API keys / wallet addresses.
All secrets are encrypted with the existing Fernet helper.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_ext.crypto_credentials import DeviceCryptoCredential
from app.services.token_encryption import encrypt_token, decrypt_token
from pydantic import BaseModel, validator
from app.models import Base
from app.database import async_engine
from datetime import datetime


router = APIRouter(prefix="/crypto-connector", tags=["crypto-connector"])

class CredentialIn(BaseModel):
    exchange: str
    api_key: str | None = None
    api_secret: str | None = None
    wallet_address: str | None = None
    chain: str | None = None

    @validator("exchange")
    def validate_exchange(cls, v: str):
        allowed = {"binance", "coinbase", "kraken", "solana", "ethereum", "bsc"}
        if v.lower() not in allowed:
            raise ValueError(f"Unsupported exchange/wallet: {v}")
        return v.lower()

class CredentialOut(CredentialIn):
    id: int
    created_at: str | None = None
    updated_at: str | None = None

# --------- CREATE / UPDATE -----------------------------------
@router.post("/", response_model=CredentialOut)
async def upsert_credential(
    cred: CredentialIn,
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    await db.run_sync(lambda s: Base.metadata.create_all(bind=async_engine.sync_engine))
    enc_key = encrypt_token(cred.api_key) if cred.api_key else None
    enc_secret = encrypt_token(cred.api_secret) if cred.api_secret else None

    def sync_upsert(session):
        obj = (
            session.query(DeviceCryptoCredential)
            .filter_by(device_id=device_id, exchange=cred.exchange)
            .first()
        )
        if not obj:
            obj = DeviceCryptoCredential(
                device_id=device_id,
                exchange=cred.exchange,
                encrypted_api_key=enc_key,
                encrypted_api_secret=enc_secret,
                wallet_address=cred.wallet_address,
                chain=cred.chain,
            )
            session.add(obj)
        else:
            obj.encrypted_api_key = enc_key
            obj.encrypted_api_secret = enc_secret
            obj.wallet_address = cred.wallet_address
            obj.chain = cred.chain
        session.commit()
        session.refresh(obj)
        # Convert datetime fields to ISO strings for response validation
        if obj.created_at:
            obj.created_at = obj.created_at.isoformat()
        return obj
    obj = await db.run_sync(sync_upsert)
    return obj

# --------- LIST --------------------------------------------
@router.get("/", response_model=list[CredentialOut])
async def list_credentials(
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    await db.run_sync(lambda s: Base.metadata.create_all(bind=async_engine.sync_engine))
    def sync_list(session):
        rows = session.query(DeviceCryptoCredential).filter_by(device_id=device_id).all()
        for r in rows:
            if r.encrypted_api_key:
                try:
                    dec = decrypt_token(r.encrypted_api_key)
                    r.api_key = f"{'*' * (len(dec) - 4)}{dec[-4:]}" if len(dec) > 4 else dec
                except Exception:
                    r.api_key = None
            else:
                r.api_key = None
            if r.encrypted_api_secret:
                try:
                    dec = decrypt_token(r.encrypted_api_secret)
                    r.api_secret = f"{'*' * (len(dec) - 4)}{dec[-4:]}" if len(dec) > 4 else dec
                except Exception:
                    r.api_secret = None
            else:
                r.api_secret = None
            # Convert datetime fields to ISO strings for Pydantic validation
            if r.created_at:
                r.created_at = r.created_at.isoformat()
            if r.updated_at:
                r.updated_at = r.updated_at.isoformat()
        return rows
    rows = await db.run_sync(sync_list)
    return rows

# --------- DELETE ------------------------------------------
@router.delete("/{cred_id}")
async def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    await db.run_sync(lambda s: Base.metadata.create_all(bind=async_engine.sync_engine))
    def sync_delete(session):
        obj = (
            session.query(DeviceCryptoCredential)
            .filter_by(id=cred_id, device_id=device_id)
            .first()
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Credential not found")
        session.delete(obj)
        session.commit()
        return {"status": "deleted"}
    result = await db.run_sync(sync_delete)
    return result
