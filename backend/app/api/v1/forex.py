"""
Forex & Currency Conversion API

Endpoints for currency conversion and exchange rates.
Supports Trove API (primary) and Alpha Vantage (fallback).
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import structlog

from app.database import async_session
from app.models import DeviceSettings
from app.services.market_data_providers import get_market_data_service
from app.services.encryption import EncryptionHelper

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/forex", tags=["forex"])


class CurrencyConversionRequest(BaseModel):
    """Request for currency conversion."""
    amount: float
    from_currency: str
    to_currency: str


class CurrencyConversionResponse(BaseModel):
    """Response for currency conversion."""
    success: bool
    amount: float
    from_currency: str
    to_currency: str
    converted_amount: float
    exchange_rate: float
    provider: str
    error: Optional[str] = None


@router.get("/rate/{from_currency}/{to_currency}")
async def get_forex_rate(
    from_currency: str,
    to_currency: str,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get current exchange rate between two currencies.

    Priority:
    1. Trove API (if configured in Settings)
    2. Alpha Vantage (fallback)

    Args:
        from_currency: Source currency (e.g., "NGN")
        to_currency: Target currency (e.g., "USD")
        device_id: Device ID header for loading settings

    Returns:
        Exchange rate data with bid/ask prices
    """
    # Load Trove settings if available
    trove_api_key = None
    trove_base_url = None
    trove_enabled = False

    if device_id:
        try:
            async with async_session() as session:
                result = await session.execute(
                    DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
                )
                settings = result.scalar_one_or_none()

                if settings and settings.trove_enabled and settings.trove_api_key:
                    trove_enabled = True
                    # Decrypt API key
                    encryption = EncryptionHelper()
                    trove_api_key = encryption.decrypt(settings.trove_api_key)
                    trove_base_url = settings.trove_base_url
        except Exception as e:
            logger.warning(f"Failed to load Trove settings: {e}")

    # Get market data service
    market_data = get_market_data_service()

    # Try Trove first if enabled
    if trove_enabled and trove_api_key and trove_base_url:
        result = await market_data._get_forex_rate_trove(
            from_currency, to_currency, trove_api_key, trove_base_url
        )
        if result.get('success'):
            return result

    # Fallback to Alpha Vantage
    result = await market_data.get_forex_rate_alphavantage(from_currency, to_currency)
    
    if not result.get('success'):
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get exchange rate: {result.get('error', 'Unknown error')}",
        )

    return result


@router.post("/convert", response_model=CurrencyConversionResponse)
async def convert_currency(
    request: CurrencyConversionRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Convert an amount from one currency to another.

    Priority:
    1. Trove API (if configured in Settings)
    2. Alpha Vantage (fallback)

    Args:
        amount: Amount to convert
        from_currency: Source currency (e.g., "NGN")
        to_currency: Target currency (e.g., "USD")
        device_id: Device ID header for loading settings

    Returns:
        Conversion result with original and converted amounts
    """
    # Load Trove settings if available
    trove_api_key = None
    trove_base_url = None
    trove_enabled = False

    if device_id:
        try:
            async with async_session() as session:
                result = await session.execute(
                    DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
                )
                settings = result.scalar_one_or_none()

                if settings and settings.trove_enabled and settings.trove_api_key:
                    trove_enabled = True
                    # Decrypt API key
                    encryption = EncryptionHelper()
                    trove_api_key = encryption.decrypt(settings.trove_api_key)
                    trove_base_url = settings.trove_base_url
        except Exception as e:
            logger.warning(f"Failed to load Trove settings: {e}")

    # Get market data service
    market_data = get_market_data_service()

    # Perform conversion
    result = await market_data.get_currency_conversion(
        amount=request.amount,
        from_currency=request.from_currency,
        to_currency=request.to_currency,
        use_trove=trove_enabled,
        trove_api_key=trove_api_key,
        trove_base_url=trove_base_url,
    )

    if not result.get('success'):
        return CurrencyConversionResponse(
            success=False,
            amount=request.amount,
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            converted_amount=0,
            exchange_rate=0,
            provider="none",
            error=result.get('error', 'Conversion failed'),
        )

    data = result.get('data', {})
    return CurrencyConversionResponse(
        success=True,
        amount=request.amount,
        from_currency=request.from_currency,
        to_currency=request.to_currency,
        converted_amount=data.get('converted_amount', 0),
        exchange_rate=data.get('exchange_rate', 0),
        provider=result.get('provider', 'unknown'),
    )


@router.get("/rates/major")
async def get_major_forex_rates(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get major forex rates (NGN/USD, EUR/USD, GBP/USD, etc.).

    Useful for currency selector UI and quick reference.

    Returns:
        Dict of currency pair -> rate
    """
    # Load Trove settings if available
    trove_api_key = None
    trove_base_url = None
    trove_enabled = False

    if device_id:
        try:
            async with async_session() as session:
                result = await session.execute(
                    DeviceSettings.__table__.select().where(DeviceSettings.device_id == device_id)
                )
                settings = result.scalar_one_or_none()

                if settings and settings.trove_enabled and settings.trove_api_key:
                    trove_enabled = True
                    encryption = EncryptionHelper()
                    trove_api_key = encryption.decrypt(settings.trove_api_key)
                    trove_base_url = settings.trove_base_url
        except Exception as e:
            logger.warning(f"Failed to load Trove settings: {e}")

    market_data = get_market_data_service()

    # Major currency pairs
    pairs = [
        ("NGN", "USD"),  # Nigerian Naira to USD
        ("USD", "NGN"),  # USD to Naira
        ("EUR", "USD"),  # Euro to USD
        ("GBP", "USD"),  # British Pound to USD
        ("USD", "JPY"),  # USD to Japanese Yen
        ("USD", "CHF"),  # USD to Swiss Franc
    ]

    rates = {}
    for from_curr, to_curr in pairs:
        pair_key = f"{from_curr}/{to_curr}"

        # Try Trove first
        if trove_enabled and trove_api_key and trove_base_url:
            result = await market_data._get_forex_rate_trove(
                from_curr, to_curr, trove_api_key, trove_base_url
            )
            if result.get('success'):
                rates[pair_key] = result['data']
                continue

        # Fallback to Alpha Vantage
        result = await market_data.get_forex_rate_alphavantage(from_curr, to_curr)
        if result.get('success'):
            rates[pair_key] = result['data']

    return {
        "success": True,
        "rates": rates,
        "timestamp": None,  # Will be populated from API responses
    }