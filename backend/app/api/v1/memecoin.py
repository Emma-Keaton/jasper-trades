"""Solana Memecoin API - DexScreener discovery (search + trending)."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import structlog

from app.services.solana_memecoin_service import get_memecoin_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/memecoin", tags=["memecoin"])


@router.get("/search")
async def memecoin_search(q: str = Query(..., min_length=1), limit: int = Query(10, le=25)):
    svc = get_memecoin_service()
    try:
        return {"results": await svc.search_tokens(q, limit=limit)}
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin search failed", error=str(e))
        raise HTTPException(status_code=502, detail="Memecoin search unavailable")


@router.get("/trending")
async def memecoin_trending(limit: int = Query(10, le=25)):
    svc = get_memecoin_service()
    try:
        return {"results": await svc.trending(limit=limit)}
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin trending failed", error=str(e))
        raise HTTPException(status_code=502, detail="Trending unavailable")


@router.get("/market/{mint}")
async def memecoin_market(mint: str):
    svc = get_memecoin_service()
    try:
        data = await svc.get_market(mint)
    except Exception as e:  # noqa: BLE001
        logger.error("Memecoin market failed", error=str(e))
        raise HTTPException(status_code=502, detail="Market data unavailable")
    if not data:
        raise HTTPException(status_code=404, detail="Token not found")
    return data
