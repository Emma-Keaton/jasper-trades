"""
System endpoints for memory monitoring and Kronos service stats.
Optimized for 4GB RAM systems.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Dict, Any
import psutil
from datetime import datetime

router = APIRouter()

KRONOS_LOCAL_AVAILABLE = False

try:
    from app.services.kronos_remote import kronos_client
    KRONOS_REMOTE_AVAILABLE = True
except ImportError:
    KRONOS_REMOTE_AVAILABLE = False


def get_memory_usage_fallback() -> Dict[str, Any]:
    """Fallback memory monitoring using psutil (no torch needed)."""
    process = psutil.Process()
    mem_info = process.memory_info()
    virtual = psutil.virtual_memory()
    
    return {
        "rss_mb": mem_info.rss / (1024 * 1024),
        "vms_mb": mem_info.vms / (1024 * 1024),
        "percent": process.memory_percent(),
        "system_available_mb": virtual.available / (1024 * 1024),
        "system_total_mb": virtual.total / (1024 * 1024),
        "system_percent": virtual.percent,
    }


@router.get("/memory")
async def memory_status() -> Dict[str, Any]:
    """
    Get current memory usage statistics.

    Critical for monitoring 4GB RAM systems during local Kronos inference.
    Note: Remote Kronos service doesn't affect local memory.
    """
    if KRONOS_LOCAL_AVAILABLE:
        from app.services.kronos import get_memory_usage, check_memory_safe
        usage = get_memory_usage()
        is_safe = check_memory_safe()
    else:
        usage = get_memory_usage_fallback()
        is_safe = usage["system_percent"] < 85.0

    return {
        **usage,
        "is_safe_for_inference": is_safe,
        "threshold_percent": 85.0,
        "status": "ok" if is_safe else "warning",
        "kronos_local_available": KRONOS_LOCAL_AVAILABLE,
        "kronos_remote_configured": KRONOS_REMOTE_AVAILABLE and kronos_client.base_url is not None,
    }


@router.get("/kronos/stats")
async def kronos_service_stats() -> Dict[str, Any]:
    """
    Get Kronos service statistics.
    
    For remote service: Returns health check result.
    For local service: Returns prediction stats (deprecated).
    """
    # Try remote service first
    if KRONOS_REMOTE_AVAILABLE and kronos_client.base_url:
        health = await kronos_client.health_check()
        return {
            "service_type": "remote",
            "url": kronos_client.base_url,
            **health
        }
    
    # Fallback to local (deprecated)
    if KRONOS_LOCAL_AVAILABLE:
        from app.services.kronos import get_service_stats
        return {
            "service_type": "local",
            **get_service_stats()
        }
    
    raise HTTPException(
        status_code=503,
        detail="Kronos service not available. Configure KRONOS_SERVICE_URL or install local dependencies."
    )


@router.get("/status")
async def system_status() -> Dict[str, Any]:
    """
    Full system status including memory and Kronos service.
    """
    if KRONOS_LOCAL_AVAILABLE:
        from app.services.kronos import get_memory_usage, check_memory_safe

        memory = get_memory_usage()
        is_safe = check_memory_safe()
    else:
        memory = get_memory_usage_fallback()
        is_safe = memory["system_percent"] < 85.0

    # Kronos status (remote preferred)
    if KRONOS_REMOTE_AVAILABLE and kronos_client.base_url:
        kronos_health = await kronos_client.health_check()
        kronos_status = {
            "type": "remote",
            "available": True,
            **kronos_health
        }
    elif KRONOS_LOCAL_AVAILABLE:
        kronos_status = {"type": "local", "available": True}
    else:
        kronos_status = {"type": "none", "available": False}

    return {
        "status": "healthy",
        "memory": memory,
        "kronos": kronos_status,
        "is_safe_for_inference": is_safe,
        "kronos_remote_url": kronos_client.base_url if KRONOS_REMOTE_AVAILABLE else None,
    }


@router.get("/pipeline-status")
async def pipeline_status(
    device_id: str = Header(None, alias="X-Device-ID"),
) -> Dict[str, Any]:
    """One-screen view of the whole automated loop: research -> prediction ->
    backtest -> strategy suite -> trading -> portfolio, across paper/demo/live."""
    from app.services import get_scheduler
    from app.services.auto_executor import get_auto_executor
    from app.services.telegram_service import telegram_service
    from app.brokers.registry import broker_registry
    from app.config import settings

    scheduler_status = get_scheduler().status() if get_scheduler() else {"running": False, "tasks": {}}
    executor_status = get_auto_executor().status()

    suite_info: Dict[str, Any] = {"total": 0, "active": 0}
    whale_info: Dict[str, Any] = {}
    if device_id:
        try:
            from app.database import async_session
            from app.services.strategy_suite import StrategySuiteService
            from app.services.solana_whale_service import last_events

            async with async_session() as db:
                suite_info = await StrategySuiteService(db).status(device_id)
            whale_info = {"recent_events": len(last_events(20))}
        except Exception:  # noqa: BLE001
            pass

    return {
        "stages": {
            "research": {
                "signal_sources_task": scheduler_status.get("tasks", {}).get("poll_signal_sources"),
                "dex_watcher_task": "dexchain-watcher (boot)",
                "whale_task": scheduler_status.get("tasks", {}).get("whale_fallback"),
            },
            "prediction": {
                "kronos": "score_kronos every 15m",
                "score_task": scheduler_status.get("tasks", {}).get("score_kronos"),
            },
            "backtest_and_strategies": {
                "evolve_task": scheduler_status.get("tasks", {}).get("strategy_evolve"),
                "refit_task": scheduler_status.get("tasks", {}).get("refit_learned"),
                "suite": suite_info,
            },
            "trading": {
                "auto_executor": {
                    "running": executor_status.get("running"),
                    "mode": executor_status.get("mode"),
                    "trades_opened": executor_status.get("trades_opened"),
                    "trades_closed": executor_status.get("trades_closed"),
                    "last_watchlist_rotation": executor_status.get("last_watchlist_rotation"),
                    "whale_pipeline": executor_status.get("whale_pipeline"),
                },
                "factor_sweep_task": scheduler_status.get("tasks", {}).get("generate_signals"),
                "brokers": broker_registry.get_stats(),
            },
            "portfolio": {
                "pnl_task": scheduler_status.get("tasks", {}).get("calculate_pnl"),
                "daily_summary_task": scheduler_status.get("tasks", {}).get("daily_summary"),
            },
        },
        "scheduler": scheduler_status,
        "environment": {
            "telegram_enabled": telegram_service.enabled,
            "groq_configured": settings.groq_configured,
            "helius_configured": bool(settings.HELIUS_API_KEY),
            "mt5_bridge_configured": bool(__import__("os").environ.get("MT5_BRIDGE_URL")),
        },
        "whale": whale_info,
    }


@router.get("/market-data")
async def market_data_status() -> Dict[str, Any]:
    """
    Get market data WebSocket status.

    Shows connection status and subscribed symbols.
    """
    try:
        from app.services.market_data_service import get_market_data_service
        service = get_market_data_service()
        status = service.get_status()
        return {
            "available": True,
            "status": "connected" if status["is_running"] else "disconnected",
            "is_running": status["is_running"],
            "subscribed_symbols": status["subscribed_symbols"],
            "subscription_count": status["subscription_count"],
        }
    except:
        return {
            "available": False,
            "status": "not_installed",
        }