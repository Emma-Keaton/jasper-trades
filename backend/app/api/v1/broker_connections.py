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

from pydantic import BaseModel
from typing import Literal

from app.database import get_db
from app.services.ctrader_oauth import CTraderOAuthService
from app.services.token_encryption import encrypt_token, decrypt_token
from app.brokers.mt5_service import get_mt5_bridge
from app.brokers import broker_registry

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


class MT5ConnectRequest(BaseModel):
    platform: Literal["mt5", "mt4"] = "mt5"
    login: str
    password: str
    server: str
    broker_name: Optional[str] = None
    account_type: Literal["demo", "live"] = "demo"  # demo = broker sandbox, live = real


class MT5ModeRequest(BaseModel):
    account_type: Literal["demo", "live"]


@router.post("/mt5/connect")
async def connect_mt5(
    req: MT5ConnectRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """Connect an MT5 (or MT4 fallback) broker account for real or demo trading.

    Credentials are encrypted at rest. The MT5 bridge is test-connected on
    save; demo accounts always succeed via the sandbox demo book, live
    accounts require a reachable terminal/bridge transport (fail-closed).
    """
    login = req.login.strip()
    if not login or not req.password.strip() or not req.server.strip():
        raise HTTPException(status_code=400, detail="login, password and server are required")

    demo = req.account_type == "demo"
    bridge = get_mt5_bridge(
        platform=req.platform,
        login=login,
        password=req.password,
        server=req.server.strip(),
        broker_name=req.broker_name,
        demo=demo,
    )
    connected = await bridge.connect()
    if not connected:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not reach the MT5/MT4 terminal for a LIVE account. "
                "Run the MetaTrader terminal on this host (Windows) or set "
                "MT5_BRIDGE_URL/MT4_BRIDGE_URL. Use account_type='demo' for the sandbox demo book."
            ),
        )

    # Attach the connected bridge to the registry so routing picks it up.
    broker_registry.register(req.platform, bridge)
    try:
        await bridge.disconnect()
    except Exception:  # noqa: BLE001
        pass
    bridge.is_connected = True  # registry placeholder stays "connected"

    existing = db.query(BrokerConnection).filter(
        BrokerConnection.device_id == device_id,
        BrokerConnection.broker_type == req.platform,
        BrokerConnection.account_id == login,
    ).first()

    if existing:
        existing.encrypted_api_key = encrypt_token(login)
        existing.encrypted_api_secret = encrypt_token(req.password)
        existing.mt5_server = req.server.strip()
        existing.account_type = req.account_type
        existing.broker_name = req.broker_name or req.server.strip()
        existing.is_connected = True
        existing.is_active = True
        existing.connection_status = "connected"
        db.commit()
        connection_id = existing.id
    else:
        connection = BrokerConnection(
            device_id=device_id,
            broker_type=req.platform,
            account_id=login,
            encrypted_api_key=encrypt_token(login),
            encrypted_api_secret=encrypt_token(req.password),
            mt5_server=req.server.strip(),
            account_type=req.account_type,
            broker_name=req.broker_name or req.server.strip(),
            account_currency="USD",
            is_connected=True,
            is_active=True,
            connection_status="connected",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        connection_id = connection.id

    return {
        "success": True,
        "id": connection_id,
        "broker_type": req.platform,
        "server": req.server,
        "account_type": req.account_type,
        "mode": "demo (sandbox)" if demo else "live (real money)",
    }


@router.post("/mt5/{connection_id}/mode")
async def set_mt5_account_mode(
    connection_id: int,
    req: MT5ModeRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """Toggle a connected MT broker account between demo (sandbox) and live."""
    connection = db.query(BrokerConnection).filter(
        BrokerConnection.id == connection_id,
        BrokerConnection.device_id == device_id,
        BrokerConnection.broker_type.in_(["mt5", "mt4"]),
    ).first()
    if not connection:
        raise HTTPException(status_code=404, detail="MT broker connection not found")

    connection.account_type = req.account_type
    db.commit()

    # Keep the in-registry bridge's paper flag in sync with the toggle.
    bridge = broker_registry.get(connection.broker_type)
    if bridge is not None and hasattr(bridge, "demo"):
        bridge.demo = req.account_type == "demo"
        bridge.is_paper_trading = bridge.demo

    return {"success": True, "id": connection_id, "account_type": req.account_type}


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
                    "account_id": conn.account_id,
                    "mt5_server": getattr(conn, "mt5_server", None),
                    "account_type": getattr(conn, "account_type", None) or "demo",
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
