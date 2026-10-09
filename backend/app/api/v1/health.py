"""
Health check endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import settings
from app.services.optional_deps import missing_optional_report

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness plus a live DB ping.

    Returns **503** when the database is unreachable. An earlier version always
    answered 200 and reported the failure only as ``"status": "degraded"`` in the
    body, which is indistinguishable from healthy to anything that checks the status
    code: Render's health check, UptimeRobot, and a load balancer all treat 200 as
    "keep this instance". A process that cannot reach its database cannot serve
    trades, so it must not look healthy.

    Absent optional dependencies are reported but do **not** affect the status code.
    They degrade a specific capability rather than the process, and folding them
    into readiness would take the service out of rotation over a missing forecasting
    library.
    """
    db_ok = False
    db_detail = "unknown"
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "ok"
    except Exception as exc:  # noqa: BLE001
        # Type and not message: the message can carry the DSN, and this response is
        # served on an unauthenticated path.
        db_detail = f"{type(exc).__name__}"

    body = {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": {"ok": db_ok, "detail": db_detail},
    }

    absent = missing_optional_report()
    if absent:
        body["optional_dependencies_absent"] = absent

    return JSONResponse(status_code=200 if db_ok else 503, content=body)