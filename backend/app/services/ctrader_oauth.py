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
import requests
from datetime import datetime, timedelta
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional, Dict


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

    # cTrader OAuth endpoints
    SANDBOX_AUTH_URL = "https://-sandbox.connect.spotware.com/oauth/authorize"
    LIVE_AUTH_URL = "https://connect.spotware.com/oauth/authorize"

    SANDBOX_TOKEN_URL = "https://-sandbox.connect.spotware.com/apps/token"
    LIVE_TOKEN_URL = "https://connect.spotware.com/apps/token"

    SANDBOX_API_URL = "https://-sandbox.api.spotware.com"
    LIVE_API_URL = "https://api.spotware.com"

    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CTRADER_REDIRECT_URI")
        self.encryption_key = os.getenv("CTRADER_ENCRYPTION_KEY")
        # Default sandbox for backward compatibility
        self.default_sandbox = os.getenv("CTRADER_SANDBOX", "true").lower() == "true"

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

    def get_authorization_url(self, is_sandbox: Optional[bool] = None) -> str:
        """
        Generate OAuth authorization URL for user redirect.

        Args:
            is_sandbox: User's environment mode (True=sandbox, False=live)
                       If None, uses default_sandbox from env

        Call this when user clicks "Connect cTrader" on the frontend.
        User will be redirected to cTrader login page.

        Returns:
            str: Full authorization URL (redirect user to this)
        """
        self._ensure_configured()
        
        # Use user's mode if provided, otherwise fall back to default
        sandbox = is_sandbox if is_sandbox is not None else self.default_sandbox
        auth_url = self.SANDBOX_AUTH_URL if sandbox else self.LIVE_AUTH_URL

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "communications information trading non_trading",
        }

        return f"{auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    def exchange_code_for_tokens(self, auth_code: str, is_sandbox: Optional[bool] = None) -> Dict:
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            auth_code: Authorization code from callback URL
            is_sandbox: User's environment mode (for API URL selection)

        Call this in your /auth/ctrader/callback endpoint.
        cTrader redirects user back with ?code=XYZ parameter.

        Returns:
            dict: {
                'access_token': str (decrypted),
                'refresh_token': str (decrypted),
                'expires_in': int (seconds),
                'expires_at': datetime
            }
        """
        sandbox = is_sandbox if is_sandbox is not None else self.default_sandbox
        token_url = self.SANDBOX_TOKEN_URL if sandbox else self.LIVE_TOKEN_URL

        payload = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        response = requests.get(token_url, params=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        if "error" in result:
            raise Exception(f"cTrader OAuth error: {result['error']} - {result.get('error_description')}")

        access_token = result.get("accessToken")
        refresh_token = result.get("refreshToken")
        expires_in = result.get("expiresIn", 2592000)  # Default 30 days

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)
        }

    def refresh_access_token(self, refresh_token: str, is_sandbox: Optional[bool] = None) -> Dict:
        """
        Refresh an expired access token using refresh token.

        Call this automatically when access token is near expiry (<24h left).

        Args:
            refresh_token: Decrypted refresh token from database
            is_sandbox: User's environment mode

        Returns:
            dict: {
                'access_token': str (decrypted),
                'expires_in': int,
                'expires_at': datetime
            }
        """
        sandbox = is_sandbox if is_sandbox is not None else self.default_sandbox
        token_url = self.SANDBOX_TOKEN_URL if sandbox else self.LIVE_TOKEN_URL

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        response = requests.get(token_url, params=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        if "error" in result:
            raise Exception(f"cTrader token refresh error: {result['error']}")

        access_token = result.get("accessToken")
        expires_in = result.get("expiresIn", 2592000)

        return {
            "access_token": access_token,
            "expires_in": expires_in,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)
        }

    def get_api_base_url(self, is_sandbox: Optional[bool] = None) -> str:
        """
        Get cTrader API base URL (sandbox or live).
        
        Args:
            is_sandbox: User's environment mode
            
        Returns:
            API base URL
        """
        sandbox = is_sandbox if is_sandbox is not None else self.default_sandbox
        return self.SANDBOX_API_URL if sandbox else self.LIVE_API_URL

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

    def get_account_info(
        self, 
        access_token: str, 
        ctid_trader_account_id: Optional[str] = None,
        is_sandbox: Optional[bool] = None,
    ) -> Dict:
        """
        Fetch account balance, equity, and metadata from cTrader API.

        Call this to sync account data periodically.

        Args:
            access_token: Decrypted access token
            ctid_trader_account_id: User's cTrader account ID
            is_sandbox: User's environment mode

        Returns:
            dict: Account info from cTrader API
        """
        api_url = f"{self.get_api_base_url(is_sandbox)}/user/accounts"
        if ctid_trader_account_id:
            api_url += f"/{ctid_trader_account_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()

        return response.json()


# Global singleton instance
ctrader_oauth = CTraderOAuthService()