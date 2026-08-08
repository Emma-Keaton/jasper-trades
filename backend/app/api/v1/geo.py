"""Geo-availability API - exposes which geo-sensitive services work from this region."""
from fastapi import APIRouter
import structlog

from app.services.geo_probe_service import get_geo_probe_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/available")
async def geo_available():
    """Return states (available/pruned) for each geo-sensitive service."""
    probe = get_geo_probe_service()
    await probe.ensure_fresh()
    return probe.status()


@router.post("/refresh")
async def geo_refresh():
    """Force a re-probe of all services."""
    probe = get_geo_probe_service()
    await probe.refresh()
    return {"success": True, "status": probe.status()}
