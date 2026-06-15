"""
Symbols API - US and Nigerian Stocks

Endpoints for fetching available trading symbols.
Sources:
1. Trove API (primary) - US + NGX stocks
2. Polygon API (fallback) - US stocks only

Bootstrap cached lists for offline fallback.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from typing import List, Dict, Any, Optional
import structlog
import httpx

from app.database import async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/symbols", tags=["symbols"])


# ============ Cached Bootstrap Data ============

# Popular Nigerian NGX stocks (cached fallback)
NGX_BOOTSTRAP = [
    {"symbol": "DANGCEM", "name": "Dangote Cement Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "MTNN", "name": "MTN Nigeria Communications Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "GTCO", "name": "Guaranty Trust Holding Company Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "AIRWAYS", "name": "Air Peace Limited", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "BUACEMENT", "name": "BUA Cement Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "SEPLAT", "name": "Seplat Energy Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "FBNH", "name": "FBN Holdings Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "ZENITHBANK", "name": "Zenith Bank Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "ACCESSCORP", "name": "Access Holdings Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "UBA", "name": "United Bank for Africa Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "FIRSTBANK", "name": "First Bank of Nigeria Holdings", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "NESTLE", "name": "Nestle Nigeria Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "TURNINGPOINT", "name": "Turning Point Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "JAPA", "name": "Japaul Gold & Ventures Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
    {"symbol": "CHAMPION", "name": "Champion Breweries Plc", "exchange": "NGX", "type": "stock", "currency": "NGN"},
]

# Popular US stocks (cached fallback)
US_BOOTSTRAP = [
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Class A", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc. Class B", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "V", "name": "Visa Inc.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "WMT", "name": "Walmart Inc.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "PG", "name": "Procter & Gamble Co.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "MA", "name": "Mastercard Inc.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "HD", "name": "Home Depot Inc.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "DIS", "name": "Walt Disney Co.", "exchange": "NYSE", "type": "stock", "currency": "USD"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "PYPL", "name": "PayPal Holdings Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "INTC", "name": "Intel Corporation", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "AMD", "name": "Advanced Micro Devices Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
]


# ============ Helper Functions ============

async def get_trove_settings(device_id: str):
    """Load Trove API configuration from database."""
    if not device_id:
        return None, None, False

    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()

            if settings and settings.trove_enabled and settings.trove_api_key:
                encryption = EncryptionHelper()
                api_key = encryption.decrypt(settings.trove_api_key)
                base_url = settings.trove_base_url or "https://sandbox.api.trovefinance.com/v1"
                return api_key, base_url, True
    except Exception as e:
        logger.warning(f"Failed to load Trove settings: {e}")

    return None, None, False


async def get_polygon_api_key(device_id: str) -> Optional[str]:
    """Load Polygon API key from database settings."""
    if not device_id:
        return None

    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            settings = result.scalar_one_or_none()

            if settings and settings.polygon_key:
                encryption = EncryptionHelper()
                return encryption.decrypt(settings.polygon_key)
    except Exception as e:
        logger.warning(f"Failed to load Polygon API key: {e}")

    return None


async def fetch_trove_symbols(
    api_key: str,
    base_url: str,
    exchange: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch symbols from Trove API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Trove API endpoints
            # GET /stocks - returns all available stocks
            # Supports filtering by exchange (US, NGX)
            
            params = {"apikey": api_key}
            
            if exchange == "US":
                params["exchange"] = "US"
            elif exchange == "NGX":
                params["exchange"] = "NGX"
            
            if search:
                params["search"] = search
            
            response = await client.get(
                f"{base_url}/stocks",
                params=params,
                headers={"Authorization": f"Bearer {api_key}"}
            )

            if response.status_code == 200:
                data = response.json()
                symbols = data.get("stocks", [])
                
                # Normalize response format
                return [
                    {
                        "symbol": s.get("symbol", ""),
                        "name": s.get("name", ""),
                        "exchange": s.get("exchange", "NGX"),
                        "type": "stock",
                        "currency": s.get("currency", "NGN" if s.get("exchange") == "NGX" else "USD"),
                    }
                    for s in symbols
                ]
            else:
                logger.warning(f"Trove API error: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Trove fetch error: {e}")
        return []


async def fetch_polygon_symbols(
    api_key: str,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch symbols from Polygon.io API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"apiKey": api_key, "limit": 100}
            
            if search:
                # Search for tickers
                response = await client.get(
                    "https://api.polygon.io/v3/reference/tickers",
                    params={**params, "search": search, "active": "true"}
                )
            else:
                # Get popular/us stocks
                response = await client.get(
                    "https://api.polygon.io/v3/reference/tickers",
                    params={**params, "market": "stocks", "active": "true", "limit": 100}
                )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                return [
                    {
                        "symbol": t.get("ticker", ""),
                        "name": t.get("name", ""),
                        "exchange": t.get("primary_exchange", "NYSE"),
                        "type": t.get("type", "stock"),
                        "currency": t.get("currency_name", "USD"),
                    }
                    for t in results[:50]  # Limit to 50
                ]
            else:
                logger.warning(f"Polygon API error: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Polygon fetch error: {e}")
        return []


def get_cached_symbols(exchange: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return cached bootstrap symbols."""
    if exchange == "NGX":
        return NGX_BOOTSTRAP
    elif exchange == "US":
        return US_BOOTSTRAP
    else:
        return NGX_BOOTSTRAP + US_BOOTSTRAP


# ============ API Endpoints ============

@router.get("")
async def list_symbols(
    exchange: Optional[str] = Query(default="all", description="Filter by exchange: all, US, NGX"),
    search: Optional[str] = Query(default=None, description="Search by symbol or name"),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get list of available trading symbols.

    Priority:
    1. Trove API (if configured) - covers both US and NGX
    2. Polygon API (fallback) - US stocks only
    3. Cached bootstrap list (offline fallback)

    Args:
        exchange: Filter by exchange (all, US, NGX)
        search: Search term for symbol or name
        device_id: Device ID header for loading API keys

    Returns:
        List of symbols with metadata
    """
    symbols = []

    # Try Trove API first
    trove_key, trove_url, trove_enabled = await get_trove_settings(device_id)

    if trove_enabled and trove_key:
        logger.info("Fetching symbols from Trove API")
        symbols = await fetch_trove_symbols(trove_key, trove_url, exchange, search)

        if symbols:
            return {
                "symbols": symbols,
                "count": len(symbols),
                "source": "trove",
                "exchange": exchange,
            }

    # Try Polygon API fallback (US only)
    if exchange in ["all", "US"]:
        polygon_key = await get_polygon_api_key(device_id)

        if polygon_key:
            logger.info("Fetching symbols from Polygon API")
            polygon_symbols = await fetch_polygon_symbols(polygon_key, search)

            if exchange == "US":
                symbols = polygon_symbols
            else:
                # Merge with NGX bootstrap
                symbols = polygon_symbols + NGX_BOOTSTRAP

    # Fallback to cached bootstrap
    if not symbols:
        logger.info("Using cached bootstrap symbols")
        symbols = get_cached_symbols(exchange if exchange != "all" else None)

        # Apply search filter if needed
        if search:
            search_lower = search.lower()
            symbols = [
                s for s in symbols
                if search_lower in s["symbol"].lower() or search_lower in s["name"].lower()
            ]

    return {
        "symbols": symbols,
        "count": len(symbols),
        "source": "cached",
        "exchange": exchange,
    }


@router.get("/popular")
async def get_popular_symbols(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get popular/trending symbols.

    Returns a curated list of popular US and NGX stocks.
    Useful for quick selectors and onboarding.
    """
    return {
        "popular": {
            "us": US_BOOTSTRAP[:10],  # Top 10 US
            "ngx": NGX_BOOTSTRAP[:10],  # Top 10 NGX
        },
        "total": 20,
    }


@router.get("/exchanges")
async def get_supported_exchanges():
    """
    Get list of supported exchanges.

    Returns metadata about supported exchanges.
    """
    return {
        "exchanges": [
            {
                "code": "US",
                "name": "United States",
                "description": "NYSE, NASDAQ, and other US exchanges",
                "currency": "USD",
                "symbol_count": len(US_BOOTSTRAP),
            },
            {
                "code": "NGX",
                "name": "Nigerian Stock Exchange",
                "description": "Lagos Stock Exchange and Nigerian markets",
                "currency": "NGN",
                "symbol_count": len(NGX_BOOTSTRAP),
            },
        ],
    }