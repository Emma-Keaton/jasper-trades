"""Crypto Connector API – per‑device storage of exchange API keys / wallet addresses.
All secrets are encrypted with the existing Fernet helper.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_ext.crypto_credentials import DeviceCryptoCredential
from app.services.token_encryption import encrypt_token, decrypt_token
from pydantic import BaseModel, validator

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
    created_at: str
    updated_at: str

# --------- CREATE / UPDATE -----------------------------------
@router.post("/", response_model=CredentialOut)
def upsert_credential(
    cred: CredentialIn,
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    enc_key = encrypt_token(cred.api_key) if cred.api_key else None
    enc_secret = encrypt_token(cred.api_secret) if cred.api_secret else None

    obj = (
        db.query(DeviceCryptoCredential)
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
        db.add(obj)
    else:
        obj.encrypted_api_key = enc_key
        obj.encrypted_api_secret = enc_secret
        obj.wallet_address = cred.wallet_address
        obj.chain = cred.chain
    db.commit()
    db.refresh(obj)
    return obj

# --------- LIST --------------------------------------------
@router.get("/", response_model=list[CredentialOut])
def list_credentials(
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    rows = (
        db.query(DeviceCryptoCredential)
        .filter_by(device_id=device_id)
        .all()
    )
    # Mask API credentials for security – do NOT expose actual keys
    for r in rows:
        # Remove any decrypted values; callers will see None (or could see a masked string)
        r.api_key = None
        r.api_secret = None
    return rows

# --------- DELETE ------------------------------------------
@router.delete("/{cred_id}")
def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    obj = (
        db.query(DeviceCryptoCredential)
        .filter_by(id=cred_id, device_id=device_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Credential not found")
    db.delete(obj)
    db.commit()
    return {"status": "deleted"}
