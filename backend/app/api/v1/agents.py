"""
Agent management endpoints.

Agents are the four specialized AI modules that each handle one stage of the
trading pipeline: Director (strategy), Quant (analysis), Risk (sizing),
Execution (order routing).  Starting an agent sets a per-device flag in
preferences and immediately triggers a factor sweep so the user sees a fast
response rather than waiting for the next scheduler tick.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field
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

async def _get_agent_config(db, device_id: str, agent_name: str) -> dict:
    """This device's overrides for one agent. Never another device's.

    Stored under ``preferences["agent_config"][<Agent>]``, alongside ``agents_started``,
    rather than on the agent object. The registry holds one instance per agent for
    the whole process, so `PUT /agents/Risk/config` used to write to a process-global
    ``max_position_usd``: every tenant traded against one user's cap, and any tenant
    could change everyone's risk budget.
    """
    prefs = await _get_device_preferences(db, device_id)
    stored = prefs.get("agent_config") or {}
    if not isinstance(stored, dict):
        return {}
    overrides = stored.get(agent_name) or {}
    return dict(overrides) if isinstance(overrides, dict) else {}


async def _set_agent_config(db, device_id: str, agent_name: str, overrides: dict) -> None:
    """Merge this device's overrides, leaving other agents and other keys alone."""
    prefs = await _get_device_preferences(db, device_id)
    stored = prefs.get("agent_config")
    if not isinstance(stored, dict):
        stored = {}
    current = stored.get(agent_name)
    merged = dict(current) if isinstance(current, dict) else {}
    merged.update(overrides)
    stored[agent_name] = merged
    prefs["agent_config"] = stored

    await _write_device_preferences(db, device_id, prefs)


async def _get_device_preferences(db, device_id: str) -> dict:
    """Read this device's preferences JSON, tolerating absent or corrupt values."""
    import json

    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    if not row or not row.preferences:
        return {}
    try:
        prefs = json.loads(row.preferences)
    except (TypeError, ValueError):
        # Corrupt JSON is treated as absent rather than raising, so one bad value
        # cannot make the settings panel unusable. The next write replaces it.
        return {}
    return prefs if isinstance(prefs, dict) else {}


async def _write_device_preferences(db, device_id: str, prefs: dict) -> None:
    """Persist preferences JSON, creating the row when this device has none."""
    import json

    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    if row:
        row.preferences = json.dumps(prefs)
    else:
        db.add(DeviceSettings(device_id=device_id, preferences=json.dumps(prefs)))
    await db.commit()


async def _set_agents_started(db, device_id: str, started: bool):
    """Persist the agents_started flag to the device's preferences JSON."""
    prefs = await _get_device_preferences(db, device_id)
    prefs["agents_started"] = started
    await _write_device_preferences(db, device_id, prefs)


async def _get_agents_started(db, device_id: str) -> bool:
    """Read the agents_started flag from preferences."""
    prefs = await _get_device_preferences(db, device_id)
    return bool(prefs.get("agents_started", False))


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

    # Trigger an immediate factor sweep for THIS device only. An unscoped sweep here
    # would open positions for every other tenant whose agents are running.
    try:
        stats = await run_factor_sweep(db, device_id=device_id)
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

    # Deliberately does NOT call agent.stop(). The registry holds one instance per
    # agent for the whole process, so stopping here cleared a process-global flag:
    # one tenant pressing Stop made /status report zero active agents for everyone
    # and start_all would not re-run until a restart. Trading for a device is gated
    # by the per-device flag written above, which is what the scheduler reads.
    return {"status": "success", "message": f"Agent {agent_name} stopped"}


class AgentConfigRequest(BaseModel):
    """Per-agent tuning overrides.

    Only the keys an agent already understands are accepted. Validation is
    per-field rather than a free-form dict, so a typo cannot silently disable a
    risk limit.

    ``extra="forbid"`` is load-bearing. With pydantic's default, an unrecognised key
    is dropped before the handler runs, so a request carrying a typo returned 200
    having changed nothing - the caller had no way to tell it did not apply. Forbidding
    extras turns that into a 422 instead of a silent no-op.
    """

    model_config = ConfigDict(extra="forbid")

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
    db=Depends(get_db),
    x_device_id: Optional[str] = Header(None),
):
    """Current tuning for one agent, plus which keys it accepts."""
    device_id = require_device_id(x_device_id)
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    allowed = AGENT_CONFIG_KEYS.get(agent.name, ())
    # Per-device overrides layered over the process defaults. The agent object
    # itself is shared by every tenant and is never mutated from a request.
    overrides = await _get_agent_config(db, device_id, agent.name)
    current = {key: overrides.get(key, agent.config.get(key)) for key in allowed}
    return {
        "agent": agent.name,
        "config": current,
        "defaults": {key: agent.config.get(key) for key in allowed},
        "accepted_keys": list(allowed),
        "device_id": device_id,
    }


@router.put("/{agent_name}/config")
async def update_agent_config(
    agent_name: str,
    config_req: AgentConfigRequest,
    db=Depends(get_db),
    x_device_id: Optional[str] = Header(None),
):
    """Update this device's tuning for one agent.

    Writes to the device's stored overrides, not to the shared agent instance. The
    previous implementation did `agent.config.update(...)` on a process-global
    object, so one tenant's settings applied to every tenant and any tenant could
    change every other tenant's risk budget.

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

    await _set_agent_config(db, device_id, agent.name, supplied)

    overrides = await _get_agent_config(db, device_id, agent.name)
    logger.info(
        "Agent config updated", agent=agent.name, device=device_id, keys=sorted(supplied)
    )
    return {
        "agent": agent.name,
        "config": {key: overrides.get(key, agent.config.get(key)) for key in allowed},
        "defaults": {key: agent.config.get(key) for key in allowed},
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
