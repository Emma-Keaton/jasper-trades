"""
Signal Sources API Endpoints

- Connect Telegram account (phone/OTP/2FA), session persisted in TelegramAccount
- List/add/remove signal sources (RSS, Reddit, StockTwits, or picked Telegram channels)
- Pick Telegram channels to watch -> each becomes a SignalSource
- Fetch + score tips, resolve, execute

Authentication: Device ID fingerprint via X-Device-ID header / localStorage.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete
import structlog

from app.database import get_db
from app.models import SignalSource, SignalTip, SourceFollow, TelegramAccount
from app.services.signal_sources.registry import get_registry
from app.services.signal_sources.ingest import (
    extract_and_ingest,
    execute_signal,
    get_signal_settings,
    maybe_auto_execute,
    save_signal_settings,
)
from app.services.signal_sources.telegram_listener import get_listener

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/signals", tags=["Signals"])


def _device_id(x_device_id: Optional[str]) -> str:
    if not x_device_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Device-ID")
    return x_device_id


class SourceCreate(BaseModel):
    source_type: str
    display_name: str
    config: Dict[str, Any] = {}
    fetch_interval_minutes: int = 30


class SourceOut(BaseModel):
    id: int
    source_type: str
    display_name: str
    config: Dict[str, Any]
    is_active: bool
    fetch_interval_minutes: int
    last_fetched_at: Optional[str] = None
    created_at: Optional[str] = None


class TelegramConnectStart(BaseModel):
    phone: str


class TelegramConnectComplete(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


class TelegramConnectOut(BaseModel):
    ok: bool
    telegram_connected: bool = False
    user: Optional[Dict[str, Any]] = None


class TelegramChannelsBody(BaseModel):
    session: Optional[str] = None


class TelegramChannelPick(BaseModel):
    channel_id: int
    title: str
    username: Optional[str] = None


class TelegramSourceCreate(BaseModel):
    channels: List[TelegramChannelPick]


class TelegramChannelsOut(BaseModel):
    channels: List[Dict[str, Any]]


class TipOut(BaseModel):
    id: int
    slug: str
    symbol: str
    side: str
    timeframe: Optional[str]
    confidence: float
    rationale: Optional[str]
    source_type: str
    source_name: str
    text: Optional[str]
    url: Optional[str]
    source_created_at: Optional[str] = None
    created_at: Optional[str] = None
    executed: bool = False
    execution_status: Optional[str] = "pending"
    execution_detail: Optional[str] = None
    executed_at: Optional[str] = None


class SignalSettingsIn(BaseModel):
    auto_execute_enabled: Optional[bool] = None
    min_confidence: Optional[float] = None
    max_position_pct: Optional[float] = None


class SignalSettingsOut(BaseModel):
    auto_execute_enabled: bool
    min_confidence: float
    max_position_pct: float


class FollowAction(BaseModel):
    source_id: int


@router.post("/sources", response_model=SourceOut)
async def create_source(
    payload: SourceCreate,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    device_id = _device_id(x_device_id)
    if payload.source_type not in ("telegram", "telegram_public", "rss", "reddit", "stocktwits"):
        raise HTTPException(status_code=400, detail="Invalid source_type")
    src = SignalSource(
        device_id=device_id,
        source_type=payload.source_type,
        config=payload.config or {},
        display_name=payload.display_name,
        fetch_interval_minutes=payload.fetch_interval_minutes,
    )
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return _source_out(src)


@router.get("/sources", response_model=List[SourceOut])
async def list_sources(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalSource).where(SignalSource.device_id == device_id))
    return [_source_out(r) for r in res.scalars().all()]


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalSource).where(SignalSource.id == source_id, SignalSource.device_id == device_id))
    src = res.scalar_one_or_none()
    if not src:
        raise HTTPException(404, "Source not found")
    await db.execute(delete(SourceFollow).where(SourceFollow.source_id == src.id))
    await db.delete(src)
    await db.commit()
    if src.source_type in ("telegram", "telegram_public"):
        await get_listener().sync(device_id)
    return {"ok": True}


# ---- Telegram connect ----

@router.post("/telegram/connect/start")
async def telegram_connect_start(payload: TelegramConnectStart, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    _device_id(x_device_id)
    reg = get_registry()
    try:
        return await reg.telegram.send_code(payload.phone)
    except RuntimeError as e:
        logger.warning("Telegram send_code misconfigured", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram send_code failed", error=str(e))
        raise HTTPException(status_code=500, detail="Could not send Telegram code")


@router.post("/telegram/connect/complete", response_model=TelegramConnectOut)
async def telegram_connect_complete(
    payload: TelegramConnectComplete,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    device_id = _device_id(x_device_id)
    reg = get_registry()
    try:
        out = await reg.telegram.sign_in(payload.phone, payload.code, payload.password)
    except ValueError:
        raise HTTPException(status_code=400, detail="2FA password required")
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram sign_in failed", error=str(e))
        raise HTTPException(status_code=500, detail="Telegram login failed")

    # Persist session in TelegramAccount (survives redeploys).
    res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = res.scalar_one_or_none()
    if not acc:
        acc = TelegramAccount(device_id=device_id, tg_phone=payload.phone)
        db.add(acc)
    user = out.get("user") or {}
    acc.tg_session = out.get("session")
    acc.tg_phone = payload.phone
    acc.tg_user_id = str(user.get("id")) if user.get("id") is not None else acc.tg_user_id
    acc.tg_username = user.get("username")
    acc.tg_first_name = user.get("first_name")
    await db.commit()

    # Start the live listener for this device (may not watch anything yet -
    # the chats filter fills in as channels are picked).
    await get_listener().sync(device_id)

    return TelegramConnectOut(ok=True, telegram_connected=True, user=user)


@router.post("/telegram/disconnect")
async def telegram_disconnect(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    await get_listener().stop(device_id)
    res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = res.scalar_one_or_none()
    if acc:
        await db.delete(acc)
        await db.commit()
    return {"ok": True}


@router.get("/telegram/account")
async def telegram_account(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = res.scalar_one_or_none()
    if not acc or not acc.tg_session:
        return {"connected": False}
    return {"connected": True, "username": acc.tg_username, "first_name": acc.tg_first_name,
            "phone": acc.tg_phone, "user_id": acc.tg_user_id}


@router.post("/telegram/channels", response_model=TelegramChannelsOut)
async def telegram_channels(
    body: Optional[TelegramChannelsBody] = None,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    device_id = _device_id(x_device_id)
    session = body.session if body and body.session else None
    if not session:
        res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
        acc = res.scalar_one_or_none()
        session = acc.tg_session if acc else None
    if not session:
        raise HTTPException(status_code=400, detail="Telegram not connected")
    reg = get_registry()
    try:
        channels = await reg.telegram.list_channels(session)
        return TelegramChannelsOut(channels=channels)
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram channels failed", error=str(e))
        raise HTTPException(status_code=500, detail="Could not list Telegram channels")


@router.post("/telegram/sources", response_model=List[SourceOut])
async def create_telegram_sources(
    payload: TelegramSourceCreate,
    x_device_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    device_id = _device_id(x_device_id)
    reg = get_registry()
    res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = res.scalar_one_or_none()
    if not acc or not acc.tg_session:
        raise HTTPException(status_code=400, detail="Telegram not connected")

    created = []
    for ch in payload.channels:
        # create one SignalSource per picked channel, referencing config channel_id
        src = SignalSource(
            device_id=device_id,
            source_type="telegram",
            display_name=ch.title or (ch.username or f"Channel {ch.channel_id}"),
            config={"channel_id": ch.channel_id, "username": ch.username or "", "title": ch.title or ""},
        )
        db.add(src)
        created.append(src)
    await db.commit()
    for s in created:
        await db.refresh(s)
    await get_listener().sync(device_id)
    return [_source_out(s) for s in created]


# ---- Follow / Unfollow ----

@router.post("/follow")
async def follow_source(payload: FollowAction, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalSource).where(SignalSource.id == payload.source_id, SignalSource.device_id == device_id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Source not found")
    existing = await db.execute(select(SourceFollow).where(SourceFollow.source_id == payload.source_id, SourceFollow.device_id == device_id))
    row = existing.scalar_one_or_none()
    if row:
        row.active = True
    else:
        db.add(SourceFollow(device_id=device_id, source_id=payload.source_id, active=True))
    await db.commit()
    return {"ok": True}


@router.delete("/follow/{source_id}")
async def unfollow_source(source_id: int, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SourceFollow).where(SourceFollow.source_id == source_id, SourceFollow.device_id == device_id))
    row = res.scalar_one_or_none()
    if row:
        row.active = False
        await db.commit()
    return {"ok": True}


# ---- Tips ----

@router.get("/tips", response_model=List[TipOut])
async def get_tips(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(
        select(SignalTip)
        .where(SignalTip.device_id == device_id)
        .order_by(desc(SignalTip.confidence), desc(SignalTip.created_at))
        .limit(50)
    )
    rows = res.scalars().all()
    return [await _tip_out(r, db) for r in rows]


@router.post("/tips/{tip_id}/resolve")
async def resolve_tip(tip_id: int, payload: Dict[str, Any], x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalTip).where(SignalTip.id == tip_id, SignalTip.device_id == device_id))
    sig = res.scalar_one_or_none()
    if not sig:
        raise HTTPException(404, "Tip not found")
    sig.pnl = payload.get("pnl")
    sig.pnl_percent = payload.get("pnl_percent")
    sig.hit = payload.get("hit")
    sig.entry_price = payload.get("entry_price") or sig.entry_price
    sig.exit_price = payload.get("exit_price")
    await db.commit()
    return {"ok": True}


@router.post("/tips/{tip_id}/execute")
async def execute_tip(tip_id: int, payload: Dict[str, Any] = None, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    """Manually execute an existing tip through the real paper/live pipeline."""
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalTip).where(SignalTip.id == tip_id, SignalTip.device_id == device_id))
    sig = res.scalar_one_or_none()
    if not sig:
        raise HTTPException(404, "Tip not found")
    result = await execute_signal(db, device_id, sig)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True, "tip_id": sig.id, **result}


@router.get("/settings", response_model=SignalSettingsOut)
async def get_settings(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    s = await get_signal_settings(db, device_id)
    return SignalSettingsOut(
        auto_execute_enabled=s.auto_execute_enabled,
        min_confidence=s.min_confidence,
        max_position_pct=s.max_position_pct,
    )


@router.post("/settings", response_model=SignalSettingsOut)
async def post_settings(payload: SignalSettingsIn, x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    s = await save_signal_settings(
        db,
        device_id,
        auto_execute_enabled=payload.auto_execute_enabled,
        min_confidence=payload.min_confidence,
        max_position_pct=payload.max_position_pct,
    )
    return SignalSettingsOut(
        auto_execute_enabled=s.auto_execute_enabled,
        min_confidence=s.min_confidence,
        max_position_pct=s.max_position_pct,
    )


@router.get("/status")
async def signals_status(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    """Runtime status for the Signals screen (listener, sources, settings)."""
    device_id = _device_id(x_device_id)
    res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = res.scalar_one_or_none()
    telegram_connected = bool(acc and acc.tg_session)
    src_res = await db.execute(
        select(SignalSource).where(
            SignalSource.device_id == device_id,
            SignalSource.source_type.in_(("telegram", "telegram_public")),
        )
    )
    watched = [_source_out(s) for s in src_res.scalars().all()]
    listener = get_listener()
    s = await get_signal_settings(db, device_id)
    return {
        "telegram_connected": telegram_connected,
        "listener_active": listener.is_running(device_id) if telegram_connected else False,
        "watched_count": len(watched),
        "auto_execute_enabled": s.auto_execute_enabled,
        "min_confidence": s.min_confidence,
        "max_position_pct": s.max_position_pct,
    }


# ---- Internal fetch/ingest (scheduler) ----

@router.post("/fetch")
async def fetch_and_ingest(x_device_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    device_id = _device_id(x_device_id)
    res = await db.execute(select(SignalSource).where(SignalSource.device_id == device_id, SignalSource.is_active == True))
    sources = res.scalars().all()
    if not sources:
        return {"ok": True, "tips": []}

    # Inject the Telegram session into telegram source configs
    tmpl: Dict[str, str] = {}
    acc_res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
    acc = acc_res.scalar_one_or_none()
    if acc:
        tmpl = {"tg_session": acc.tg_session or ""}

    cfg_list = []
    for s in sources:
        cfg = {"source_type": s.source_type, "source_id": str(s.id), **(s.config or {})}
        if s.source_type == "telegram":
            cfg.update(tmpl)
        cfg_list.append(cfg)

    reg = get_registry()
    drafts = await reg.fetch_all(cfg_list, limit=50)
    saved = await extract_and_ingest(db, device_id, drafts)
    for sig in saved:
        await maybe_auto_execute(db, device_id, sig)
    await db.commit()
    return {"ok": True, "tips": [await _tip_out(s, db) for s in saved]}


# ---- mappers ----

def _source_out(src: SignalSource) -> Dict[str, Any]:
    return {
        "id": src.id,
        "source_type": src.source_type,
        "display_name": src.display_name,
        "config": src.config or {},
        "is_active": src.is_active,
        "fetch_interval_minutes": src.fetch_interval_minutes,
        "last_fetched_at": src.last_fetched_at.isoformat() if src.last_fetched_at else None,
        "created_at": src.created_at.isoformat() if src.created_at else None,
    }


async def _tip_out(sig: SignalTip, db: AsyncSession) -> Dict[str, Any]:
    src_name = ""
    src_type = ""
    src = await db.get(SignalSource, sig.source_id)
    if src:
        src_name = src.display_name
        src_type = src.source_type
    return {
        "id": sig.id,
        "slug": sig.slug,
        "symbol": sig.symbol,
        "side": sig.side,
        "timeframe": sig.timeframe,
        "confidence": sig.confidence,
        "rationale": sig.rationale,
        "source_type": src_type,
        "source_name": src_name,
        "text": sig.text,
        "url": sig.url,
        "source_created_at": sig.source_created_at.isoformat() if sig.source_created_at else None,
        "created_at": sig.created_at.isoformat() if sig.created_at else None,
        "executed": sig.executed,
        "execution_status": sig.execution_status or "pending",
        "execution_detail": sig.execution_detail,
        "executed_at": sig.executed_at.isoformat() if sig.executed_at else None,
    }

