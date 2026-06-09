"""
Swarm API - Parallel factor research with swarm intelligence
"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import structlog

from app.services.swarm_service import swarm_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/swarm", tags=["Swarm Intelligence"])


class SwarmRunRequest(BaseModel):
    """Swarm run request"""
    task_type: str = Field(..., description="Task type (alpha_bench, factor_research)")
    factors: List[str] = Field(..., description="List of factor IDs to test")
    symbol: str = Field(..., description="Ticker symbol")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    worker_count: int = Field(5, ge=1, le=10, description="Number of parallel workers")


@router.post("/run")
async def run_swarm(request: SwarmRunRequest):
    """
    Start a swarm run for parallel factor research.
    
    **What it does:**
    1. Splits factor research into N subtasks
    2. Dispatches to worker agents in parallel
    3. Monitors progress via task files
    4. Aggregates results on completion
    
    **10x Faster Than Sequential:**
    - 100 factors tested in <10 minutes (vs 100min sequential)
    - Parallel backtesting across workers
    - Crash recovery from task files
    
    **Strict Alpha Bench:**
    - Random control factors catch beta-tracking
    - OOS (out-of-sample) split validation
    - Only significant factors pass
    
    Returns run ID for tracking progress.
    """
    try:
        run_id = await swarm_service.run_swarm(
            task_type=request.task_type,
            factors=request.factors,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            worker_count=request.worker_count,
        )
        
        return {
            "status": "started",
            "run_id": run_id,
            "total_tasks": len(request.factors),
            "worker_count": request.worker_count,
            "estimated_completion_minutes": len(request.factors) / request.worker_count * 0.5,
        }
        
    except Exception as e:
        logger.error(f"Swarm run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}")
async def get_swarm_status(run_id: str):
    """
    Get status of a swarm run.
    
    Returns:
    - Progress percentage
    - Completed/failed task count
    - Worker status
    - Results (if complete)
    """
    result = swarm_service.get_swarm_status(run_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/list")
async def list_swarms(limit: int = Query(20, ge=1, le=100)):
    """List recent swarm runs"""
    return {
        "swarms": swarm_service.get_all_swarms(limit),
        "total": len(swarm_service.swarms),
    }


@router.post("/{run_id}/retry")
async def retry_failed_tasks(run_id: str):
    """
    Retry failed tasks in a swarm run.
    
    Retries tasks that failed with retry_count < 3.
    Useful for transient failures (network, timeout).
    """
    retried = await swarm_service.retry_failed_tasks(run_id)
    return {
        "status": "success",
        "tasks_retried": retried,
    }


@router.post("/reap-stale")
async def reap_stale_runs():
    """
    Reap stale/stuck swarm runs.
    
    Marks runs as "stale" if running > 10 minutes without completion.
    Call this periodically to clean up stuck runs.
    """
    reap_count = await swarm_service.reap_stale_runs()
    return {
        "status": "success",
        "runs_marked_stale": reap_count,
    }


@router.get("/status")
async def get_swarm_service_status():
    """Get swarm service status"""
    return swarm_service.get_status()