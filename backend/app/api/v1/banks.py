"""
Nigerian Bank List API

Fetches active Nigerian banks from payment gateways (Paystack/Flutterwave).
Returns bank names and NIP codes for payout processing.

Gateway Priority:
1. Paystack (most reliable, widely used)
2. Flutterwave (fallback)
3. Monnify (alternative)

All gateway credentials are loaded from Settings page (encrypted in database).
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Dict, Any, Optional
import structlog
import httpx

from app.database import async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["banks"])


async def get_paystack_api_key() -> Optional[str]:
    """Get Paystack API key from settings."""
    async with async_session() as session:
        result = await session.execute(DeviceSettings.__table__.select().limit(1))
        settings = result.scalar_one_or_none()
        
        if settings and settings.naira_bank_details:
            encryption = EncryptionHelper()
            bank_config = encryption.decrypt_json(settings.naira_bank_details)
            if bank_config:
                # Paystack key stored in bank_config or use general payment config
                return bank_config.get("paystack_api_key")
    return None


@router.get("/nigeria")
async def get_nigerian_banks(
    gateway: str = "paystack",  # paystack, flutterwave, monnify
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get list of active Nigerian banks with NIP codes.

    Dynamically fetches from payment gateway to ensure:
    - Always up-to-date bank list
    - Accurate bank codes for transfers
    - Includes new digital banks and MFBs

    Args:
        gateway: Payment gateway to query (paystack recommended)
        device_id: Device ID for loading API keys

    Returns:
        List of banks with name, code, slug
    """
    # Load API key from settings
    api_key = None
    
    if device_id:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()
            
            if settings:
                encryption = EncryptionHelper()
                
                # Try to get Paystack key from naira_bank_details
                if settings.naira_bank_details:
                    bank_config = encryption.decrypt_json(settings.naira_bank_details)
                    if bank_config:
                        api_key = bank_config.get("paystack_api_key")
                
                # Fallback: check if there's a general payment_config
                # (implementation depends on your settings structure)

    # If no API key configured, return cached list
    if not api_key:
        logger.warning("No payment gateway API key configured, returning cached bank list")
        return get_cached_nigerian_banks()

    # Fetch from gateway
    if gateway == "paystack":
        banks = await fetch_paystack_banks(api_key)
    elif gateway == "flutterwave":
        banks = await fetch_flutterwave_banks(api_key)
    elif gateway == "monnify":
        banks = await fetch_monnify_banks(api_key)
    else:
        banks = await fetch_paystack_banks(api_key)  # Default to Paystack

    if not banks:
        # Fallback to cached list
        logger.warning("Gateway fetch failed, returning cached bank list")
        return get_cached_nigerian_banks()

    return {"banks": banks, "source": gateway, "updated_at": None}


@router.get("/nigeria/validate")
async def validate_nigerian_account(
    account_number: str,
    bank_code: str,
    gateway: str = "paystack",
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Validate Nigerian bank account and return account holder name.

    Uses CBN-mandated NIP account resolution to prevent fraud.
    Verifies that the account number matches the registered name.

    Args:
        account_number: 10-digit NUBAN account number
        bank_code: Bank NIP code (e.g., "058" for GTBank)
        gateway: Payment gateway to use (paystack or flutterwave)
        device_id: Device ID for loading API keys

    Returns:
        Account holder name and validation status

    Example:
        GET /api/v1/banks/nigeria/validate?account_number=0123456789&bank_code=058
        Response: {"success": true, "account_name": "JOHN DOE", "account_number": "0123456789"}
    """
    # Validate account number format (NUBAN = 10 digits)
    if not account_number or len(account_number) != 10 or not account_number.isdigit():
        return {
            "success": False,
            "message": "Invalid account number. Must be 10 digits.",
            "error_code": "INVALID_ACCOUNT_NUMBER",
        }

    # Load API key from settings
    api_key = None
    
    if device_id:
        async with async_session() as session:
            result = await session.execute(
                DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()
            
            if settings and settings.naira_bank_details:
                encryption = EncryptionHelper()
                bank_config = encryption.decrypt_json(settings.naira_bank_details)
                if bank_config:
                    api_key = bank_config.get("paystack_api_key")

    if not api_key:
        return {
            "success": False,
            "message": "Payment gateway API key not configured. Please add your Paystack/Flutterwave key in Settings.",
            "error_code": "NO_API_KEY",
        }

    # Validate using gateway
    if gateway == "paystack":
        result = await validate_account_paystack(account_number, bank_code, api_key)
    elif gateway == "flutterwave":
        result = await validate_account_flutterwave(account_number, bank_code, api_key)
    else:
        result = await validate_account_paystack(account_number, bank_code, api_key)

    return result


async def fetch_paystack_banks(api_key: str) -> List[Dict[str, str]]:
    """Fetch Nigerian banks from Paystack API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.paystack.co/bank",
                params={"country": "nigeria", "use_cursor": "false"},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                banks_data = data.get("data", [])
                
                # Extract only needed fields
                return [
                    {
                        "name": bank.get("name", ""),
                        "code": bank.get("code", ""),  # NIP code
                        "slug": bank.get("slug", ""),
                        "ussd": bank.get("ussd", None),  # USSD code if available
                    }
                    for bank in banks_data
                    if bank.get("active", True)  # Only active banks
                ]
            else:
                logger.error(f"Paystack API error: {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"Paystack fetch error: {e}")
        return []


async def fetch_flutterwave_banks(api_key: str) -> List[Dict[str, str]]:
    """Fetch Nigerian banks from Flutterwave API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.flutterwave.com/v3/banks",
                params={"country": "NG"},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                banks_data = data.get("data", [])
                
                return [
                    {
                        "name": bank.get("bank_name", ""),
                        "code": str(bank.get("code", "")),
                        "slug": bank.get("slug", ""),
                    }
                    for bank in banks_data
                ]
                
    except Exception as e:
        logger.error(f"Flutterwave fetch error: {e}")
        return []


async def fetch_monnify_banks(api_key: str) -> List[Dict[str, str]]:
    """Fetch Nigerian banks from Monnify API."""
    # Monnify requires OAuth token exchange first, skipping for brevity
    logger.warning("Monnify bank fetch not implemented, use Paystack or Flutterwave")
    return []


async def validate_account_paystack(
    account_number: str,
    bank_code: str,
    api_key: str,
) -> Dict[str, Any]:
    """
    Validate Nigerian bank account using Paystack.

    Args:
        account_number: 10-digit NUBAN account number
        bank_code: Bank code (e.g., "058" for GTBank)
        api_key: Paystack secret key

    Returns:
        Account holder name if successful, error message otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.paystack.co/bank/resolve",
                params={
                    "account_number": account_number,
                    "bank_code": bank_code,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") is True:
                    account_data = data.get("data", {})
                    return {
                        "success": True,
                        "account_name": account_data.get("account_name", ""),
                        "account_number": account_number,
                        "bank_code": bank_code,
                        "message": "Account validated successfully",
                    }
                else:
                    return {
                        "success": False,
                        "message": data.get("message", "Could not resolve account"),
                        "error_code": "RESOLVE_FAILED",
                    }
            else:
                return {
                    "success": False,
                    "message": f"Paystack API error: {response.status_code}",
                    "error_code": "API_ERROR",
                }

    except httpx.RequestError as e:
        logger.error(f"Paystack validation error: {e}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}",
            "error_code": "CONNECTION_ERROR",
        }


async def validate_account_flutterwave(
    account_number: str,
    bank_code: str,
    api_key: str,
) -> Dict[str, Any]:
    """
    Validate Nigerian bank account using Flutterwave.

    Args:
        account_number: 10-digit NUBAN account number
        bank_code: Bank code
        api_key: Flutterwave secret key

    Returns:
        Account holder name if successful, error message otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.flutterwave.com/v3/accounts/resolve",
                json={
                    "account_number": account_number,
                    "account_bank": bank_code,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    account_data = data.get("data", {})
                    return {
                        "success": True,
                        "account_name": account_data.get("account_name", ""),
                        "account_number": account_number,
                        "bank_code": bank_code,
                        "message": data.get("message", "Account resolved"),
                    }
                else:
                    return {
                        "success": False,
                        "message": data.get("message", "Could not resolve account"),
                        "error_code": "RESOLVE_FAILED",
                    }
            else:
                return {
                    "success": False,
                    "message": f"Flutterwave API error: {response.status_code}",
                    "error_code": "API_ERROR",
                }

    except httpx.RequestError as e:
        logger.error(f"Flutterwave validation error: {e}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}",
            "error_code": "CONNECTION_ERROR",
        }


def get_cached_nigerian_banks() -> Dict[str, Any]:
    """
    Return cached list of major Nigerian banks with NIP codes.
    
    This is used when no payment gateway API key is configured.
    In production, you should always configure a gateway key.
    
    Includes:
    - Traditional commercial banks (Tier 1 & 2)
    - Neobanks, digital banks, and MFBs
    - Payment Service Banks (PSBs)
    
    Bank codes sourced from Paystack/Flutterwave APIs.
    NIP (NIBSS) codes included for direct clearing integration.
    """
    banks = [
        # ═══════════════════════════════════════════════════════════════
        # Tier 1 Traditional Commercial Banks
        # ═══════════════════════════════════════════════════════════════
        {"name": "Access Bank", "code": "044", "nip_code": "000014", "slug": "access-bank"},
        {"name": "Guaranty Trust Bank (GTBank)", "code": "058", "nip_code": "000013", "slug": "gtbank"},
        {"name": "Zenith Bank", "code": "057", "nip_code": "000015", "slug": "zenith-bank"},
        {"name": "United Bank for Africa (UBA)", "code": "033", "nip_code": "000004", "slug": "uba"},
        {"name": "First Bank of Nigeria", "code": "011", "nip_code": "000016", "slug": "first-bank"},
        {"name": "Fidelity Bank", "code": "070", "nip_code": "000007", "slug": "fidelity-bank"},
        {"name": "Stanbic IBTC Bank", "code": "221", "nip_code": "000012", "slug": "stanbic-ibtcbank"},
        {"name": "Sterling Bank", "code": "232", "nip_code": "000001", "slug": "sterling-bank"},
        {"name": "Wema Bank", "code": "035", "nip_code": "000017", "slug": "wema-bank"},
        {"name": "First City Monument Bank (FCMB)", "code": "214", "nip_code": "000003", "slug": "fcmb"},
        {"name": "Union Bank of Nigeria", "code": "032", "nip_code": "000018", "slug": "union-bank"},
        {"name": "Polaris Bank", "code": "076", "nip_code": "000008", "slug": "polaris-bank"},
        {"name": "Keystone Bank", "code": "082", "nip_code": "000002", "slug": "keystone-bank"},
        {"name": "Ecobank Nigeria", "code": "050", "nip_code": "000010", "slug": "ecobank-nigeria"},
        {"name": "Providus Bank", "code": "101", "nip_code": "000023", "slug": "providus-bank"},
        {"name": "Globus Bank", "code": "103", "nip_code": "000027", "slug": "globus-bank"},
        {"name": "Titan Trust Bank", "code": "102", "nip_code": "000025", "slug": "titan-trust-bank"},
        {"name": "PremiumTrust Bank", "code": "105", "nip_code": "000031", "slug": "premiumtrust-bank"},
        {"name": "Signature Bank", "code": "106", "nip_code": "000034", "slug": "signature-bank"},
        {"name": "Optimus Bank", "code": "107", "nip_code": "000036", "slug": "optimus-bank"},
        {"name": "Lotus Bank", "code": "303", "nip_code": "000029", "slug": "lotus-bank"},
        
        # ═══════════════════════════════════════════════════════════════
        # Neobanks, Digital Banks & Microfinance Banks (MFBs)
        # ═══════════════════════════════════════════════════════════════
        {"name": "OPay (Paycom)", "code": "999992", "nip_code": "100004", "slug": "opay"},
        {"name": "PalmPay", "code": "999991", "nip_code": "100033", "slug": "palmpay"},
        {"name": "Kuda Bank", "code": "50211", "nip_code": "090267", "slug": "kuda-bank"},
        {"name": "Moniepoint MFB", "code": "50515", "nip_code": "090405", "slug": "moniepoint-mfb"},
        {"name": "Carbon MFB", "code": "565", "nip_code": "100026", "slug": "carbon"},
        {"name": "VFD Microfinance Bank (Vbank)", "code": "566", "nip_code": "090110", "slug": "vfd-mfb"},
        {"name": "FairMoney MFB", "code": "51318", "nip_code": "090328", "slug": "fairmoney"},
        {"name": "Rubies MFB", "code": "125", "nip_code": "090175", "slug": "rubies-mfb"},
        {"name": "ALAT by Wema", "code": "035A", "nip_code": "090270", "slug": "alat"},
        {"name": "Gomoney", "code": "90117", "nip_code": "090317", "slug": "gomoney"},
        {"name": "Sparkle", "code": "90116", "nip_code": "090316", "slug": "sparkle"},
        {"name": "Bankly", "code": "90115", "nip_code": "090315", "slug": "bankly"},
        {"name": "Fundall (via Providus)", "code": "90114", "nip_code": "090314", "slug": "fundall"},
        
        # ═══════════════════════════════════════════════════════════════
        # Payment Service Banks (PSBs) - Telco-led
        # ═══════════════════════════════════════════════════════════════
        {"name": "MoMo PSB (MTN)", "code": "120003", "nip_code": "120003", "slug": "momo-psb"},
        {"name": "SmartCash PSB (Airtel)", "code": "120004", "nip_code": "120004", "slug": "smartcash-psb"},
        {"name": "9PSB (9mobile)", "code": "120001", "nip_code": "120001", "slug": "9psb"},
    ]
    
    return {
        "banks": banks,
        "source": "cached",
        "updated_at": None,
        "note": "Configure Paystack/Flutterwave API key in Settings for live bank list",
        "total": len(banks),
    }