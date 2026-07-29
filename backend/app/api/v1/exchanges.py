"""Endpoint to expose supported exchange identifiers for the frontend.
Uses the CCXT library (if installed) to list all available exchange IDs.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/exchanges", tags=["exchanges"])

@router.get("/", response_model=list[str])
def list_exchanges():
    try:
        import ccxt
        # Return sorted list of exchange IDs (lowercase)
        return sorted([e.lower() for e in ccxt.exchanges])
    except Exception:
        # If CCXT is not installed, fall back to a minimal static list
        return ["binance", "coinbase", "kraken", "solana", "ethereum", "bsc"]
