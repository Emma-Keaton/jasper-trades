"""
Health check endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint (includes a live DB ping)."""
    db_ok = False
    db_detail = "unknown"
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "ok"
    except Exception as exc:  # noqa: BLE001
        db_detail = f"error: {exc}"

    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": {"ok": db_ok, "detail": db_detail},
    }
