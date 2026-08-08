"""
cTrader OpenAPI OAuth 2.0 Authentication Service

Handles the complete OAuth flow:
1. Generate authorization URL for user redirect
2. Exchange authorization code for access/refresh tokens
3. Refresh expired tokens automatically
4. Encrypt/decrypt tokens for secure storage

Architecture:
- Users never share broker passwords with us
- OAuth tokens are encrypted at rest using Fernet (AES-128)
- Tokens are only decrypted in memory during API calls
- Users can revoke access anytime from broker dashboard
- Per-user sandbox/live mode via environment_mode field
"""

import os
import secrets
import httpx
import structlog
from datetime import datetime, timedelta
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional, Dict

logger = structlog.get_logger(__name__)

# cTrader OAuth endpoints - LIVE ONLY (cTrader = live trading; all paper trading
# goes through the Universal Paper Trading engine, so the sandbox endpoints are
# intentionally removed to prevent accidental use of a malformed sandbox URL).
LIVE_AUTH_URL = "https://connect.spotware.com/oauth/authorize"
LIVE_TOKEN_URL = "https://connect.spotware.com/apps/token"
LIVE_API_URL = "https://api.spotware.com"


class CTraderOAuthService:
    """
    cTrader OpenAPI OAuth 2.0 service.

    Environment Variables Required:
    - CTRADER_CLIENT_ID: Your app's Client ID from cTrader Connect
    - CTRADER_CLIENT_SECRET: Your app's Client Secret
    - CTRADER_REDIRECT_URI: Callback URL (e.g., https://your-app.onrender.com/auth/ctrader/callback)
    - CTRADER_ENCRYPTION_KEY: Fernet key for encrypting tokens (generate with Fernet.generate_key())
    
    Note: CTRADER_SANDBOX is deprecated - use per-user environment_mode field instead
    """

    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CTRADER_REDIRECT_URI")
        self.encryption_key = os.getenv("CTRADER_ENCRYPTION_KEY")

        # Initialize Fernet encryption only if key is available
        self.encryptor = None
        if self.encryption_key:
            self.encryptor = Fernet(self.encryption_key.encode())

        # Check if configured (don't raise error, just track state)
        self._is_configured = all([self.client_id, self.client_secret, self.redirect_uri, self.encryption_key])

    def _ensure_configured(self):
        """Raise error if not configured - call this before using OAuth features."""
        if not self._is_configured:
            raise ValueError(
                "cTrader OAuth not configured. "
                "Set CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_REDIRECT_URI, CTRADER_ENCRYPTION_KEY in Render dashboard"
            )

    # === Public Methods ===

    def get_authorization_url(self, state: Optional[str] = None, is_sandbox: Optional[bool] = None) -> str:
        """
        Generate the LIVE OAuth authorization URL for user redirect.

        Includes a random `state` param (CSRF protection) that must be validated
        on the callback. cTrader is LIVE-only in this app; paper trading is
        handled by the Universal Paper Trading engine.
        """
        self._ensure_configured()
        # URL-encode params defensively.
        from urllib.parse import urlencode

        state = state or secrets.token_urlsafe(16)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "communications information trading non_trading",
            "state": state,
        }
        return f"{LIVE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, auth_code: str) -> Dict:
        """
        Exchange authorization code for access/refresh tokens (async, live).
        """
        self._ensure_configured()
        payload = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(LIVE_TOKEN_URL, data=payload)
            response.raise_for_status()
            result = response.json()

        if "error" in result:
            desc = result.get("error_description")
            logger.error("cTrader OAuth code exchange failed", error=result["error"], detail=desc)
            raise Exception(f"cTrader OAuth error: {result['error']}")

        access_token = result.get("accessToken")
        refresh_token = result.get("refreshToken")
        expires_in = result.get("expiresIn", 2592000)  # 30 days

        if not access_token or not refresh_token:
            raise Exception("cTrader did not return access/refresh tokens")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh an expired access token using the refresh token (async, live).

        Also returns a possibly-rotated refresh token if the server issues one.
        """
        self._ensure_configured()
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(LIVE_TOKEN_URL, data=payload)
            response.raise_for_status()
            result = response.json()

        if "error" in result:
            logger.error("cTrader token refresh failed", error=result["error"])
            raise Exception(f"cTrader token refresh error: {result['error']}")

        access_token = result.get("accessToken")
        expires_in = result.get("expiresIn", 2592000)
        new_refresh_token = result.get("refreshToken")

        return {
            "access_token": access_token,
            # Include a new refresh token IF the server rotates it.
            "refresh_token": new_refresh_token,
            "expires_in": expires_in,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
        }

    def get_api_base_url(self, is_sandbox: Optional[bool] = None) -> str:
        """cTrader API base URL - LIVE only."""
        del is_sandbox  # sandbox intentionally unsupported
        return LIVE_API_URL

    # === Token Encryption (Security) ===

    def encrypt_token(self, token: str) -> str:
        """
        Encrypt token before storing in database.

        Uses Fernet symmetric encryption (AES-128).
        The encryption key must be stored securely in environment variables.
        """
        self._ensure_configured()
        token_bytes = token.encode('utf-8')
        encrypted = self.encryptor.encrypt(token_bytes)
        return encrypted.decode('utf-8')

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt token for API use.

        Only call this in memory when making API calls.
        Never log or expose decrypted tokens.
        """
        self._ensure_configured()
        try:
            encrypted_bytes = encrypted_token.encode('utf-8')
            decrypted = self.encryptor.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except InvalidToken:
            raise Exception("Invalid encryption key or corrupted token")

    # === Utility Methods ===

    async def get_account_info(
        self,
        access_token: str,
        ctid_trader_account_id: Optional[str] = None,
        is_sandbox: Optional[bool] = None,
    ) -> Dict:
        """
        Fetch account balance, equity, and metadata from cTrader API (async).

        Call this to sync account data periodically. FAILS CLOSED: raises on any
        HTTP error so callers never treat an expired token as a valid account.
        """
        del is_sandbox
        api_url = f"{self.get_api_base_url()}/user/accounts"
        if ctid_trader_account_id:
            api_url += f"/{ctid_trader_account_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            return response.json()


# Global singleton instance
ctrader_oauth = CTraderOAuthService()