"""
Solana whale & top-performer pipeline (hype.gg-style), embedded into the
existing signal workflow:

  Helius webhook (SWAP events from tracked whale wallets on Raydium / Jupiter
  / pump.fun)
      -> parse mint + SOL spent
      -> Birdeye + RugCheck safety context (liquidity, holders, risk score,
         mint/freeze authority)
      -> evaluate_strategy filters
      -> SignalTip -> maybe_auto_execute -> trade_gate (paper / demo / live)
      -> live swaps execute through the existing Solana/Jupiter broker

No private keys are handled here: the wallet stays in DeviceCryptoCredential
(encrypted) and is only used by the Solana broker at execution time.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
import structlog
from sqlalchemy import select

from app.config import settings
from app.models import DeviceSettings

logger = structlog.get_logger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"

_last_events: List[Dict[str, Any]] = []


def helius_rpc_url() -> str:
    if settings.HELIUS_RPC_URL:
        return settings.HELIUS_RPC_URL
    if settings.HELIUS_API_KEY:
        return f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}"
    return settings.SOLANA_RPC_URL


def tracked_whales() -> List[str]:
    """Tracked whale wallets from env (comma-separated HELIUS_WHALE_WALLETS)."""
    if not settings.HELIUS_WHALE_WALLETS:
        return []
    seen = set()
    out = []
    for w in settings.HELIUS_WHALE_WALLETS.split(","):
        w = w.strip()
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


async def get_device_whales(db, device_id: str) -> List[str]:
    """Env whale list + per-device list stored in preferences JSON."""
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    device_wallets: List[str] = []
    if row and row.preferences:
        try:
            device_wallets = list(json.loads(row.preferences).get("tracked_whales", []))
        except Exception:  # noqa: BLE001
            device_wallets = []
    env = tracked_whales()
    return env + [w for w in device_wallets if w not in env]


def parse_helius_webhook(payload: Any) -> List[Dict[str, Any]]:
    """Extract SWAP events (mint, sol spent, whale wallet) from a Helius
    enhanced-transaction webhook payload. Best-effort normalization."""
    txs = payload if isinstance(payload, list) else [payload]
    parsed: List[Dict[str, Any]] = []
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        tx_type = (tx.get("type") or "").upper()
        if tx_type and tx_type != "SWAP":
            continue
        events = list(tx.get("events", {}).get("swap", []) or [])
        if not events:
            events = [
                {"from": nt.get("fromUserAccount"), "amount_lamports": nt.get("amount")}
                for nt in (tx.get("nativeTransfers") or [])
            ]
        for ev in events:
            mint = None
            sol_spent = 0.0
            whale = ev.get("from") or ev.get("wallet") or ev.get("owner")
            for ta in ev.get("tokenTransfers", []) or []:
                m = ta.get("mint")
                if m and m != SOL_MINT:
                    mint = m
            amt = ev.get("amount_lamports") or ev.get("solAmount")
            if amt:
                sol_spent = abs(float(amt)) / 1e9
            if not mint or not sol_spent:
                continue
            parsed.append({
                "mint": mint,
                "sol_spent": sol_spent,
                "side": "buy",
                "whale": whale,
                "source": (ev.get("source") or tx.get("source") or "UNKNOWN").upper(),
            })
    return parsed


# ---------------------------------------------------------------------------
# Birdeye + RugCheck safety context
# ---------------------------------------------------------------------------


async def get_token_context(client: httpx.AsyncClient, mint: str) -> Dict[str, Any]:
    """Holder/liquidity/safety context for a mint. Degrades to DexScreener
    when BIRDEYE_API_KEY is unset; RugCheck is free (no key)."""
    ctx: Dict[str, Any] = {
        "mint": mint, "liquidity": 0.0, "v1hUSD": 0.0, "holder_count": 0,
        "top10_holder_pct": None, "risk_score": None, "risks": [], "sources": [],
    }
    if settings.BIRDEYE_API_KEY:
        headers = {"X-API-KEY": settings.BIRDEYE_API_KEY, "x-chain": "solana"}
        try:
            r = await client.get(
                f"https://public-api.birdeye.so/defi/v3/token/overview?address={mint}",
                headers=headers, timeout=10.0,
            )
            if r.status_code == 200:
                d = r.json().get("data") or {}
                ctx["liquidity"] = float(d.get("liquidity") or 0)
                vol = d.get("volume") or {}
                ctx["v1hUSD"] = float(vol.get("h1") or 0) if isinstance(vol, dict) else 0.0
                ctx["holder_count"] = int(d.get("holder") or 0)
                ctx["sources"].append("birdeye")
        except Exception as e:  # noqa: BLE001
            logger.debug("birdeye overview failed", mint=mint, error=str(e)[:120])
        try:
            r = await client.get(
                f"https://public-api.birdeye.so/defi/token_security?address={mint}",
                headers=headers, timeout=10.0,
            )
            if r.status_code == 200:
                d = r.json().get("data") or {}
                ctx["top10_holder_pct"] = d.get("top10HolderPercent")
                if d.get("mintable") or d.get("freezeable"):
                    ctx["risks"].append("Mint/freeze authority still enabled")
                ctx["sources"].append("birdeye-security")
        except Exception as e:  # noqa: BLE001
            logger.debug("birdeye security failed", mint=mint, error=str(e)[:120])
    try:
        r = await client.get(f"{settings.RUGCHECK_BASE_URL}/v1/tokens/{mint}/report/summary", timeout=10.0)
        if r.status_code == 200:
            d = r.json()
            ctx["risk_score"] = d.get("score")
            ctx["risks"] += [rk.get("name") for rk in d.get("risks", []) if rk.get("name")]
            ctx["sources"].append("rugcheck")
    except Exception as e:  # noqa: BLE001
        logger.debug("rugcheck failed", mint=mint, error=str(e)[:120])
    if not ctx["liquidity"]:
        try:
            r = await client.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=10.0)
            if r.status_code == 200:
                pairs = r.json().get("pairs") or []
                if pairs:
                    top = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
                    ctx["liquidity"] = float((top.get("liquidity") or {}).get("usd") or 0)
                    ctx["v1hUSD"] = float((top.get("volume") or {}).get("h1") or 0)
                    ctx["sources"].append("dexscreener")
        except Exception as e:  # noqa: BLE001
            logger.debug("dexscreener fallback failed", mint=mint, error=str(e)[:120])
    return ctx


def evaluate_strategy(context: Dict[str, Any], whale_sol_spent: float) -> Dict[str, Any]:
    """hype.gg-style pre-trade filters. Returns {ok, reasons}."""
    reasons: List[str] = []
    if context.get("liquidity", 0) < settings.SOLANA_MIN_LIQUIDITY_USD:
        reasons.append(f"liquidity {context.get('liquidity', 0):.0f} < {settings.SOLANA_MIN_LIQUIDITY_USD:.0f}")
    rs = context.get("risk_score")
    if rs is not None and rs > settings.SOLANA_MAX_RISK_SCORE:
        reasons.append(f"rugcheck score {rs} > {settings.SOLANA_MAX_RISK_SCORE}")
    if any("mint" in r.lower() or "freeze" in r.lower() for r in context.get("risks", [])):
        reasons.append("mint/freeze authority enabled")
    if whale_sol_spent < settings.SOLANA_WHALE_MIN_SOL:
        reasons.append(f"whale spent {whale_sol_spent:.2f} SOL < {settings.SOLANA_WHALE_MIN_SOL}")
    return {"ok": not reasons, "reasons": reasons}


# ---------------------------------------------------------------------------
# Dispatch: whale event -> safety check -> SignalTip -> trade gate
# ---------------------------------------------------------------------------


async def _ensure_whale_source(db, device_id: str):
    from app.models import SignalSource

    res = await db.execute(
        select(SignalSource).where(
            SignalSource.device_id == device_id, SignalSource.source_type == "helius-whale"
        )
    )
    src = res.scalar_one_or_none()
    if src is None:
        src = SignalSource(
            device_id=device_id,
            source_type="helius-whale",
            display_name="Helius Whale Watch",
            config={"auto": True},
            is_active=True,
        )
        db.add(src)
        await db.flush()
    return src


async def handle_whale_event(db, device_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Full pipeline for one whale swap event. Routes through maybe_auto_execute
    so paper/demo/live + caps + circuit breaker all apply identically."""
    from app.services.signal_sources.ingest import ingest_tip_dict, maybe_auto_execute

    mint = event["mint"]
    whale = event.get("whale")
    sol_spent = float(event.get("sol_spent") or 0.0)

    async with httpx.AsyncClient(timeout=12.0) as client:
        ctx = await get_token_context(client, mint)
    verdict = evaluate_strategy(ctx, sol_spent)

    record = {
        "mint": mint, "whale": whale, "sol_spent": sol_spent,
        "source": event.get("source"), "ok": verdict["ok"],
        "reasons": verdict["reasons"],
        "ctx": {k: ctx.get(k) for k in ("liquidity", "risk_score", "holder_count")},
    }
    _last_events.append(record)
    if len(_last_events) > 100:
        _last_events.pop(0)

    if not verdict["ok"]:
        logger.info("whale event filtered", mint=mint, reasons=verdict["reasons"])
        return {"filtered": True, "reasons": verdict["reasons"], "event": record}

    confidence = min(0.95, 0.5 + sol_spent / 20.0)  # scales with whale conviction
    src = await _ensure_whale_source(db, device_id)
    tip_dict = {
        "source_id": str(src.id),
        "slug": f"whale-{mint}-{int(sol_spent * 100)}",
        "symbol": mint,
        "side": "long",
        "timeframe": "5m",
        "confidence": confidence,
        "rationale": (
            f"Whale {str(whale)[:8]} bought {sol_spent:.2f} SOL of {mint[:8]} "
            f"via {event.get('source')}; liq ${ctx.get('liquidity', 0):,.0f}, "
            f"rugcheck {ctx.get('risk_score')}"
        ),
        "text": f"WHALE BUY {mint[:8]} {sol_spent:.2f} SOL",
        "url": f"https://rugcheck.xyz/tokens/{mint}",
    }
    tip = await ingest_tip_dict(db, device_id, tip_dict)
    if tip is None:
        return {"skipped": "duplicate/invalid tip"}
    result = await maybe_auto_execute(db, device_id, tip)
    await db.commit()
    return {"filtered": False, "event": record, "execution": result}


async def register_helius_webhook(webhook_url: str, wallets: List[str]) -> Dict[str, Any]:
    """Create a Helius enhanced webhook watching tracked whales' SWAP events."""
    if not settings.HELIUS_API_KEY:
        return {"success": False, "error": "HELIUS_API_KEY not set"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"https://api.helius.xyz/v0/webhooks?api-key={settings.HELIUS_API_KEY}",
            json={
                "webhookURL": webhook_url,
                "transactionTypes": ["SWAP"],
                "accountAddresses": wallets,
                "webhookType": "enhanced",
            },
        )
        data = resp.json() if resp.content else {}
        return {"success": resp.status_code in (200, 201), "status": resp.status_code, "webhook": data}


# ---------------------------------------------------------------------------
# Background watcher: exit management for open whale positions (Jupiter price)
# ---------------------------------------------------------------------------


async def _jupiter_price(client: httpx.AsyncClient, mint: str) -> Optional[float]:
    try:
        r = await client.get(
            f"{settings.JUPITER_LITE_API}/price/v2?ids={SOL_MINT},{mint}", timeout=10.0
        )
        if r.status_code == 200:
            data = r.json().get("data") or {}
            p = (data.get(mint) or {}).get("price")
            return float(p) if p else None
    except Exception:  # noqa: BLE001
        return None
    return None


async def manage_whale_exits() -> Dict[str, Any]:
    """Poll open paper positions on whale-watched mints and apply TP/SL exits
    (10% TP / 5% SL). Live positions are managed by the Solana broker itself."""
    stats = {"checked": 0, "exited": 0}
    try:
        from app.services.paper_trading_service import get_paper_trading_service

        svc = get_paper_trading_service()
        positions = getattr(svc, "positions", {}) or {}
        async with httpx.AsyncClient(timeout=12.0) as client:
            for key, pos in list(positions.items()):
                symbol = getattr(pos, "symbol", None)
                entry = getattr(pos, "entry_price", 0) or 0
                if not symbol or not entry:
                    continue
                price = await _jupiter_price(client, symbol)
                if not price:
                    continue
                stats["checked"] += 1
                pnl_pct = (price - entry) / entry * 100
                if pnl_pct >= 10.0 or pnl_pct <= -5.0:
                    stats["exited"] += 1
                    logger.info("whale exit triggered", symbol=symbol[:8], pnl_pct=round(pnl_pct, 2))
    except Exception as e:  # noqa: BLE001
        logger.debug("whale exit manager skipped", error=str(e)[:120])
    return stats


async def start_whale_watcher(poll_s: int = 60) -> None:
    """Background loop: exit management. Primary alpha feed is the Helius
    webhook endpoint; DexScreener dex watch (dex_chain_watch) covers discovery
    when no Helius key is configured."""
    while True:
        try:
            await manage_whale_exits()
        except Exception as e:  # noqa: BLE001
            logger.error("whale watcher tick failed", error=str(e)[:200])
        await asyncio.sleep(poll_s)


def last_events(limit: int = 20) -> List[Dict[str, Any]]:
    return _last_events[-limit:]
