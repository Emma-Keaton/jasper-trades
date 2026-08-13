"""
cTrader OpenAPI OAuth Authentication API

Endpoints for users to connect their cTrader accounts securely via OAuth.
Users authorize your app from cTrader's login page (never share broker password).

Flow:
1. User clicks "Connect cTrader" → calls GET /api/v1/ctrader/connect
2. Frontend redirects user to returned authorization URL
3. User logs in on cTrader (id.ctrader.com) and authorizes
4. cTrader redirects back to callback with ?code=XYZ
5. Backend exchanges code for tokens, saves encrypted to database
6. User's account is now connected for auto-trading

Authentication: Device ID fingerprint via localStorage (no user accounts)
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query, Header
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid
import structlog

from app.database import get_db
from app.services.ctrader_oauth import CTraderOAuthService

import_structlog_logger = structlog.get_logger(__name__)
logger = import_structlog_logger

# Import BrokerConnection from models_ext directory (renamed from models to avoid conflict with models.py)
from app.models_ext.broker_connections import BrokerConnection

router = APIRouter(prefix="/brokers", tags=["brokers"])

oauth_service = CTraderOAuthService()


def get_device_id(x_device_id: Optional[str] = Header(None)) -> str:
    """Get device ID from header or generate new one."""
    if x_device_id:
        return x_device_id
    return str(uuid.uuid4())


# Module-level in-memory store of issued OAuth states per device (CSRF protection).
# On restart states are lost, which only forces a fresh connect - safe.
_oauth_states: dict[str, str] = {}


@router.get("/connect")
async def connect_ctrader(
    mode: str = Query(default="live", description="Trading mode: must be 'live'"),
    device_id: str = Depends(get_device_id),
):
    """
    Get cTrader OAuth authorization URL (LIVE only) with a CSRF `state`.

    Frontend calls this, then redirects the user to the returned URL. The user
    is redirected to cTrader's secure login page; the issued `state` must be
    returned on the callback (preventing CSRF).
    """
    if not oauth_service.client_id:
        raise HTTPException(
            status_code=500,
            detail="cTrader OAuth not configured. Set CTRADER_CLIENT_ID in environment."
        )

    # Enforce live-only mode – sandbox/development should use Universal Paper Trading
    if mode.lower() != "live":
        raise HTTPException(
            status_code=400,
            detail="cTrader sandbox mode is not supported. Use Universal Paper Trading for paper trading."
        )

    # Issue a CSRF state bound to this device, then build the LIVE auth URL.
    state = str(uuid.uuid4().hex)
    _oauth_states[state] = device_id
    auth_url = oauth_service.get_authorization_url(state=state)

    return {
        "authorization_url": auth_url,
        "state": state,
        "mode": "live",
        "message": "Redirect user to this URL to connect cTrader account for live trading"
    }



@router.get("/callback")
async def ctrader_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """
    OAuth callback endpoint.

    cTrader redirects here after user authorizes. Validates the CSRF `state`,
    exchanges the code for tokens, saves them encrypted, then redirects to the
    frontend settings page. No token or exception details are leaked to the
    client on failure.
    """
    # Validate CSRF state (defence against login CSRF).
    # The state is bound to the device that started the flow, so we recover the
    # real device id from it here (the callback cannot carry the X-Device-ID header).
    resolved_device_id = _oauth_states.pop(state, None) if state else None
    if not resolved_device_id:
        return RedirectResponse(
            url="/?ctrader_error=Invalid+state+(CSRF+protection)",
            status_code=302,
        )
    device_id = resolved_device_id

    # Handle OAuth errors
    if error:
        error_msg = {
            "access_denied": "You denied access to your account",
            "invalid_scope": "Invalid permissions requested",
            "invalid_client": "Invalid Client ID/Secret configuration"
        }.get(error, "OAuth authorization failed")
        return RedirectResponse(
            url=f"/?ctrader_error={error_msg}",
            status_code=302
        )

    if not code:
        return RedirectResponse(
            url="/?ctrader_error=No+authorization+code+received",
            status_code=302
        )

    try:
        # Exchange code for tokens (async)
        token_data = await oauth_service.exchange_code_for_tokens(code)

        # Fetch account info from cTrader API (async)
        account_info = await oauth_service.get_account_info(token_data["access_token"])

        # Extract account details
        ctid_account_id = account_info.get("ctidTraderAccountId")
        accounts = account_info.get("accounts", [])
        if not accounts:
            raise Exception("No trading accounts found")

        first_account = accounts[0]
        broker_name = account_info.get("broker", {}).get("name", "Unknown Broker")
        account_currency = first_account.get("currency")
        account_balance = first_account.get("balance", 0.0)

        # Encrypt tokens for storage using the cTrader OAuth encryptor
        # (CTRADER_ENCRYPTION_KEY, fail-closed) so the token-refresh scheduler
        # can decrypt them with the SAME key.
        encrypted_access = oauth_service.encrypt_token(token_data["access_token"])
        encrypted_refresh = oauth_service.encrypt_token(token_data["refresh_token"])

        # Create or update broker connection
        existing = db.query(BrokerConnection).filter(
            BrokerConnection.ctrader_account_id == ctid_account_id
        ).first()

        if existing:
            # Update existing connection
            existing.encrypted_access_token = encrypted_access
            existing.encrypted_refresh_token = encrypted_refresh
            existing.token_expires_at = token_data["expires_at"]
            existing.is_connected = True
            existing.connection_status = "connected"
            existing.broker_name = broker_name
            existing.account_currency = account_currency
            existing.account_balance = account_balance
            db.commit()
            connection_id = existing.id
        else:
            # Create new connection
            connection = BrokerConnection(
                device_id=device_id,
                broker_type="ctrader",
                ctrader_account_id=ctid_account_id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expires_at=token_data["expires_at"],
                broker_name=broker_name,
                account_currency=account_currency,
                account_balance=account_balance,
                is_connected=True,
                connection_status="connected"
            )
            db.add(connection)
            db.commit()
            db.refresh(connection)
            connection_id = connection.id

        # Redirect to frontend with success
        return RedirectResponse(
            url=f"/?ctrader_connected=true&id={connection_id}",
            status_code=302
        )

    except Exception as e:
        # Log details server-side only; never leak exception/token info to client.
        logger.error("cTrader OAuth callback failed", error=str(e))
        return RedirectResponse(
            url="/?ctrader_error=Connection+failed",
            status_code=302
        )


@router.post("/disconnect/{connection_id}")
async def disconnect_ctrader(
    connection_id: int,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """
    Disconnect cTrader account.

    Clears tokens and disables auto-trading.
    User can reconnect anytime.
    """
    connection = db.query(BrokerConnection).filter(
        BrokerConnection.id == connection_id,
        BrokerConnection.device_id == device_id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    connection.is_connected = False
    connection.connection_status = "disconnected"
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.is_active = False
    db.commit()

    return {"message": "cTrader account disconnected"}


@router.get("/accounts")
async def get_ctrader_accounts(
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """Get all connected broker accounts for current device"""
    try:
        connections = db.query(BrokerConnection).filter(
            BrokerConnection.device_id == device_id
        ).all()

        return {
            "accounts": [
                {
                    "id": conn.id,
                    "broker_name": conn.broker_name or conn.broker_type,
                    "broker_type": conn.broker_type,
                    "account_balance": conn.account_balance or 0.0,
                    "account_currency": conn.account_currency or "USD",
                    "is_connected": conn.is_connected,
                    "is_active": conn.is_active,
                    "connected_at": conn.created_at.isoformat() if conn.created_at else None
                }
                for conn in connections
            ]
        }
    except Exception as e:
        # Return empty list if table doesn't exist or query fails
        return {
            "accounts": [],
            "message": "No broker accounts connected",
            "error": str(e)
        }
