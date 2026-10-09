"""
Agent management endpoints.

Agents are the four specialized AI modules that each handle one stage of the
trading pipeline: Director (strategy), Quant (analysis), Risk (sizing),
Execution (order routing).  Starting an agent sets a per-device flag in
preferences and immediately triggers a factor sweep so the user sees a fast
response rather than waiting for the next scheduler tick.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
import structlog

from app.agents import agent_registry
from app.database import get_db
from app.services.factor_trading import run_factor_sweep

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _set_agents_started(db, device_id: str, started: bool):
    """Persist the agents_started flag to the device's preferences JSON."""
    import json
    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    prefs: dict = {}
    if row and row.preferences:
        try:
            prefs = json.loads(row.preferences)
        except (TypeError, ValueError):
            prefs = {}
    prefs["agents_started"] = started
    if row:
        row.preferences = json.dumps(prefs)
    else:
        row = DeviceSettings(device_id=device_id, preferences=json.dumps(prefs))
        db.add(row)
    await db.commit()


async def _get_agents_started(db, device_id: str) -> bool:
    """Read the agents_started flag from preferences."""
    import json
    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    if not row or not row.preferences:
        return False
    try:
        prefs = json.loads(row.preferences)
        return bool(prefs.get("agents_started", False))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

from app.device_auth import require_device_id

@router.get("")
async def list_agents():
    """List all registered agents."""
    return {"agents": [agent.get_stats() for agent in agent_registry.get_all()]}


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.get_stats()


@router.post("/{agent_name}/start")
async def start_agent(
    agent_name: str,
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db=Depends(get_db),
):
    """Start an agent: persist the flag, trigger an immediate factor sweep."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    device_id = require_device_id(x_device_id)
    # Persist the "started" flag so the scheduler respects it too
    await _set_agents_started(db, device_id, True)

    # Flip the in-memory flag
    await agent.start()

    # Trigger an immediate factor sweep for this device
    try:
        stats = await run_factor_sweep(db)
        logger.info(
            "Immediate factor sweep after agent start",
            agent=agent_name,
            device=device_id,
            traded=stats.get("traded", 0),
        )
    except Exception as exc:
        logger.warning("Immediate sweep failed", error=str(exc))
        stats = {}

    return {
        "status": "success",
        "message": f"Agent {agent_name} started",
        "sweep": stats,
    }


@router.post("/{agent_name}/stop")
async def stop_agent(
    agent_name: str,
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db=Depends(get_db),
):
    """Stop an agent: persist the flag so the scheduler skips this device."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    device_id = require_device_id(x_device_id)
    await _set_agents_started(db, device_id, False)
    await agent.stop()

    return {"status": "success", "message": f"Agent {agent_name} stopped"}


class AgentConfigRequest(BaseModel):
    """Per-agent tuning overrides.

    Only the keys an agent already understands are accepted. Validation is
    per-field rather than a free-form dict, so a typo cannot silently disable a
    risk limit.
    """

    max_position_usd: Optional[float] = Field(default=None, gt=0)
    max_portfolio_risk_pct: Optional[float] = Field(default=None, gt=0, le=100)
    default_stop_loss_pct: Optional[float] = Field(default=None, gt=0, le=100)
    smart_routing: Optional[bool] = None
    default_order_type: Optional[str] = Field(default=None, pattern="^(market|limit|stop|stop_limit)$")


#: Only these keys may be set per agent. Anything else is rejected rather than
#: stored, so a typo does not look like it took effect.
AGENT_CONFIG_KEYS = {
    "Risk": ("max_position_usd", "max_portfolio_risk_pct", "default_stop_loss_pct"),
    "Execution": ("smart_routing", "default_order_type"),
    # Director and Quant take no tuning parameters.
    "Director": (),
    "Quant": (),
}


@router.get("/{agent_name}/config")
async def get_agent_config(
    agent_name: str,
    x_device_id: Optional[str] = Header(None),
):
    """Current tuning for one agent, plus which keys it accepts."""
    device_id = require_device_id(x_device_id)
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    allowed = AGENT_CONFIG_KEYS.get(agent.name, ())
    current = {
        key: agent.config.get(key)
        for key in allowed
    }
    return {
        "agent": agent.name,
        "config": current,
        "accepted_keys": list(allowed),
        "device_id": device_id,
    }


@router.put("/{agent_name}/config")
async def update_agent_config(
    agent_name: str,
    config_req: AgentConfigRequest,
    x_device_id: Optional[str] = Header(None),
):
    """Update one agent's tuning.

    Rejects unknown keys. The previous behaviour - no endpoint at all - meant the
    frontend's settings panel silently did nothing.
    """
    device_id = require_device_id(x_device_id)
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    allowed = AGENT_CONFIG_KEYS.get(agent.name)
    if allowed is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown agent '{agent.name}'"
        )

    supplied = {
        key: value
        for key, value in config_req.model_dump().items()
        if value is not None
    }
    rejected = sorted(set(supplied) - set(allowed))
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{agent.name} does not accept {rejected}. "
                f"Accepted keys: {sorted(allowed) or 'none'}."
            ),
        )

    agent.config.update(supplied)
    # The agents read some of these into attributes at construction time, so
    # refresh them rather than leaving the attribute stale.
    if agent.name == "Risk":
        if "max_position_usd" in supplied:
            agent.max_position_usd = supplied["max_position_usd"]
        if "max_portfolio_risk_pct" in supplied:
            agent.max_portfolio_risk_pct = supplied["max_portfolio_risk_pct"]
        if "default_stop_loss_pct" in supplied:
            agent.default_stop_loss_pct = supplied["default_stop_loss_pct"]
    if agent.name == "Execution":
        if "smart_routing" in supplied:
            agent.smart_routing = supplied["smart_routing"]
        if "default_order_type" in supplied:
            agent.default_order_type = supplied["default_order_type"]

    logger.info(
        "Agent config updated", agent=agent.name, device=device_id, keys=sorted(supplied)
    )
    return {
        "agent": agent.name,
        "config": {key: agent.config.get(key) for key in allowed},
        "accepted_keys": list(allowed),
        "device_id": device_id,
    }


@router.get("/{agent_name}/stats")
async def get_agent_stats(agent_name: str):
    """Get agent performance statistics."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.get_stats()
