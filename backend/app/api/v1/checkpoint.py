"""
Checkpoint API - Crash recovery with state persistence
"""
from fastapi import APIRouter, Body, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import structlog

from app.services.checkpoint_service import checkpoint_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/checkpoint", tags=["Checkpoint Resume"])


@router.post("/enable")
async def enable_checkpointing():
    """Enable checkpointing for crash recovery"""
    checkpoint_service.enable()
    return {
        "status": "enabled",
        "checkpoint_dir": str(checkpoint_service.checkpoint_dir),
    }


@router.post("/disable")
async def disable_checkpointing():
    """Disable checkpointing"""
    checkpoint_service.disable()
    return {"status": "disabled"}


@router.get("/status/{ticker}")
async def get_checkpoint_status(ticker: str):
    """
    Get checkpoint status for a ticker.
    
    Shows if checkpoint exists, last step, and creation time.
    """
    return checkpoint_service.get_checkpoint_status(ticker)


@router.get("/list")
async def list_checkpoints():
    """List all checkpoint databases"""
    return {
        "checkpoints": checkpoint_service.list_checkpoints(),
        "total": len(checkpoint_service.list_checkpoints()),
    }


@router.post("/clear/{ticker}")
async def clear_checkpoints(ticker: str):
    """Clear checkpoints for a specific ticker"""
    cleared = checkpoint_service.clear_checkpoints(ticker)
    return {
        "status": "cleared",
        "ticker": ticker,
        "checkpoints_cleared": cleared,
    }


@router.post("/clear-all")
async def clear_all_checkpoints():
    """Clear ALL checkpoints"""
    cleared = checkpoint_service.clear_checkpoints()
    return {
        "status": "cleared_all",
        "checkpoints_cleared": cleared,
    }


@router.post("/resume/{ticker}")
async def resume_from_checkpoint(
    ticker: str,
    run_id: Optional[str] = Body(None),
):
    """
    Resume analysis from checkpoint.
    
    Returns state from last successful step.
    Use this to continue after a crash.
    """
    result = checkpoint_service.resume_from_checkpoint(ticker, run_id)
    
    if not result:
        return {
            "status": "no_checkpoint",
            "message": f"No checkpoint found for {ticker}",
        }
    
    return result


@router.post("/save")
async def save_checkpoint(
    ticker: str = Body(...),
    step: str = Body(...),
    state: Dict[str, Any] = Body(...),
    run_id: Optional[str] = Body(None),
):
    """
    Manually save a checkpoint.
    
    Useful for long-running custom analyses.
    """
    checkpoint_service.save_checkpoint(ticker, step, state, run_id)
    return {
        "status": "saved",
        "ticker": ticker,
        "step": step,
    }


@router.post("/cleanup")
async def cleanup_old_checkpoints(
    days: int = Body(7, ge=1, le=30),
):
    """
    Remove checkpoints older than N days.
    
    Call this periodically to clean up disk space.
    """
    removed = checkpoint_service.cleanup_old_checkpoints(days)
    return {
        "status": "success",
        "checkpoints_removed": removed,
        "age_threshold_days": days,
    }


@router.get("/status")
async def get_service_status():
    """Get checkpoint service status"""
    return {
        "enabled": checkpoint_service.enabled,
        "checkpoint_dir": str(checkpoint_service.checkpoint_dir),
        "total_checkpoints": len(checkpoint_service.list_checkpoints()),
    }