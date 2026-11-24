"""
Strategy Suite — unifies alpha factors, Kronos/self-learning and backtesting
into one loop, driven by the free-model Strategy Architect.

Flow (hand in hand):
  1. Architect (LLM, task="director") proposes a strategy spec from the
     learner summary + recent backtest results.
  2. BacktestService validates it on real OHLCV.
  3. If the hit-rate beats coin-flip with enough samples and meets the
     device's confidence target, the strategy is PROMOTED to active.
  4. Active strategies evaluate the (rotating top-performer) watchlist in the
     factor sweep; signals route through the same trade gate (paper/demo/live).
  5. Scored outcomes feed strategy_learner.fit -> the next proposal is better.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StrategyRecord, WatchlistItem
from app.services.strategy_learner import beats_coin_flip

logger = structlog.get_logger(__name__)


class StrategySuiteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # LLM helper: route through the side-by-side provider picked for the
    # task (NIM/Groq/Gemini per settings), env key as fallback.
    # ------------------------------------------------------------------
    async def _llm_json(self, device_id: str, task: str, prompt: str) -> Dict[str, Any]:
        from app.services.llm_providers import PROVIDERS, resolve_task_model
        from app.config import settings as app_settings
        from app.models import DeviceSettings
        from app.services.encryption import EncryptionHelper

        res = await self.db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
        row = res.scalar_one_or_none()
        selections: Dict[str, Any] = {}
        if row and row.llm_model_selections:
            try:
                selections = json.loads(row.llm_model_selections)
            except Exception:  # noqa: BLE001
                selections = {}
        available = [p for p in PROVIDERS if getattr(app_settings, PROVIDERS[p]["env_key"], None)]
        if row is not None:
            for prov, col in (("groq", "groq_key"), ("gemini", "gemini_key"), ("nvidia", "nvidia_key")):
                enc = getattr(row, col, None)
                if enc:
                    try:
                        if EncryptionHelper().decrypt(enc) and prov not in available:
                            available.append(prov)
                    except Exception:  # noqa: BLE001
                        pass
        routing = resolve_task_model(task, selections, available or ["groq"])
        provider, model = routing["provider"], routing["model"]

        messages = [
            {"role": "system", "content": "You are a trading strategy architect. Reply with STRICT JSON only."},
            {"role": "user", "content": prompt},
        ]
        if provider == "groq":
            from app.services.llm_service import get_llm_client

            text = await get_llm_client().chat_completion(messages, task_type=task)
        else:
            from app.services.llm_providers import ProviderLLMClient

            key = getattr(app_settings, PROVIDERS[provider]["env_key"], None) or ""
            if not key and row is not None:
                enc = getattr(row, {"gemini": "gemini_key", "nvidia": "nvidia_key"}[provider], None)
                if enc:
                    key = EncryptionHelper().decrypt(enc) or ""
            if not key:
                raise RuntimeError(f"no key for provider {provider}")
            client = ProviderLLMClient(provider, key, model)
            text = await client.chat_completion(messages, model=model, temperature=0.3, max_tokens=1200)
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        return {}


    # ------------------------------------------------------------------
    # Architect: propose -> backtest -> promote
    # ------------------------------------------------------------------
    async def propose_strategy(self, device_id: str, target_confidence: float = 70.0) -> Dict[str, Any]:
        from app.services.auto_executor import get_auto_executor
        from app.services.backtest_service import BacktestService

        learner_summary = get_auto_executor().get_learner_summary()
        recent = await self.list_strategies(device_id, limit=5)
        recent_desc = [
            {"name": r["name"], "status": r["status"], "hit_rate": r.get("hit_rate"), "confidence": r.get("confidence")}
            for r in recent
        ]
        # Ground the proposal in REAL catalog ids so factor_ids always resolve.
        from app.services.alpha_factor_service import AlphaFactorService

        catalog = AlphaFactorService(self.db).alpha_factors
        catalog_ids = [f["id"] for f in catalog]
        sample_ids = catalog_ids[:60]
        prompt = (
            "Design ONE trading strategy as JSON with keys: name, factor_ids (list of alpha factor ids), "
            "min_confidence (0-100), take_profit_pct, stop_loss_pct, position_size_usd, timeframe. "
            f"The alpha factor catalog has {len(catalog_ids)} factors; pick 3-6 REAL ids from this list only: "
            f"{json.dumps(sample_ids)} (plus any of the other {len(catalog_ids) - len(sample_ids)} catalog ids if relevant). "
            f"Learner summary: {json.dumps(learner_summary)[:800]}. "
            f"Recent strategies: {json.dumps(recent_desc)}. "
            f"Target confidence {target_confidence}."
        )
        try:
            spec = await self._llm_json(device_id, "director", prompt)
        except Exception as e:  # noqa: BLE001
            logger.warning("architect LLM propose failed", device=device_id, error=str(e))
            return {"success": False, "error": f"llm propose failed: {e}"}
        if not spec.get("name") or not spec.get("factor_ids"):
            return {"success": False, "error": "architect returned no usable spec", "raw": spec}

        # Keep only factor ids that exist in the real catalog.
        from app.services.alpha_factor_service import AlphaFactorService

        catalog_ids = {f["id"] for f in AlphaFactorService(self.db).alpha_factors}
        spec["factor_ids"] = [fid for fid in spec.get("factor_ids", []) if fid in catalog_ids]
        if not spec["factor_ids"]:
            return {"success": False, "error": "architect picked no valid catalog factor ids", "raw": spec}

        # Backtest the proposal on real OHLCV before it can go active.
        bt = BacktestService(self.db)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=90)
        try:
            bt_result = await bt.run_backtest(
                strategy_name=spec["name"],
                factor_ids=list(spec.get("factor_ids", []))[:8],
                start_date=start,
                end_date=end,
                initial_capital=10000.0,
                assets=None,
            )
        except Exception as e:  # noqa: BLE001
            bt_result = {"success": False, "error": str(e)}

        total = int(bt_result.get("total_trades", 0)) if bt_result.get("success") else 0
        hit_rate = float(bt_result.get("win_rate", 0.0)) if bt_result.get("success") else 0.0
        wins = int(hit_rate * total)
        significant = bool(bt_result.get("success")) and beats_coin_flip(wins, total)
        status = "active" if (significant and hit_rate * 100 >= float(spec.get("min_confidence", 0))) else "draft"

        rec = StrategyRecord(
            device_id=device_id,
            name=str(spec["name"])[:128],
            spec=json.dumps(spec),
            status=status,
            backtest=json.dumps(bt_result)[:4000],
            confidence=float(spec.get("min_confidence", 0.0)),
            hit_rate=hit_rate,
            sample_size=total,
            promoted_at=datetime.utcnow() if status == "active" else None,
        )
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        logger.info("Strategy proposed", device=device_id, name=rec.name, status=status, hit_rate=hit_rate, n=total)
        return {"success": True, "strategy": self._row_dict(rec)}

    # ------------------------------------------------------------------
    # CRUD / status
    # ------------------------------------------------------------------
    async def list_strategies(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        res = await self.db.execute(
            select(StrategyRecord)
            .where(StrategyRecord.device_id == device_id)
            .order_by(StrategyRecord.created_at.desc())
            .limit(limit)
        )
        return [self._row_dict(r) for r in res.scalars().all()]

    async def set_status(self, device_id: str, strategy_id: int, status: str) -> Dict[str, Any]:
        if status not in ("draft", "active", "retired"):
            return {"success": False, "error": "invalid status"}
        res = await self.db.execute(
            select(StrategyRecord).where(
                StrategyRecord.id == strategy_id, StrategyRecord.device_id == device_id
            )
        )
        rec = res.scalar_one_or_none()
        if rec is None:
            return {"success": False, "error": "not found"}
        rec.status = status
        if status == "active":
            rec.promoted_at = datetime.utcnow()
        elif status == "retired":
            rec.retired_at = datetime.utcnow()
        await self.db.commit()
        return {"success": True, "strategy": self._row_dict(rec)}



# ---------------------------------------------------------------------------
# Suite cycle: evaluate the rotating top-performer watchlist with the active
# strategies and route through the same trade gate as every other signal.
# ---------------------------------------------------------------------------

async def run_suite_cycle(db: AsyncSession, *, device_id: Optional[str] = None) -> Dict[str, Any]:
    from app.models import SignalSource, SignalTip
    from app.services.factor_trading import _is_agents_started, _fetch_ohlcv, _build_panel
    from app.services.alpha_factor_service import AlphaFactorService
    from app.services.signal_sources.ingest import get_signal_settings, maybe_auto_execute
    from app.config import settings

    stats: Dict[str, Any] = {"devices": 0, "evaluated": 0, "traded": 0, "skipped": 0, "details": []}
    suite = StrategySuiteService(db)

    if device_id is not None:
        device_ids = [device_id]
    else:
        res = await db.execute(select(WatchlistItem.device_id).distinct())
        device_ids = [r[0] for r in res.all()]

    for dev in device_ids:
        if not await _is_agents_started(db, dev):
            continue
        active = [s for s in await suite.list_strategies(dev) if s["status"] == "active"]
        if not active:
            continue
        stats["devices"] += 1
        s = await get_signal_settings(db, dev)
        if not s.auto_execute_enabled:
            continue
        source_res = await db.execute(
            select(SignalSource).where(
                SignalSource.device_id == dev, SignalSource.source_type == "factor"
            )
        )
        source = source_res.scalar_one_or_none()
        if source is None:
            continue

        items = (
            await db.execute(select(WatchlistItem).where(WatchlistItem.device_id == dev))
        ).scalars().all()
        factor_service = AlphaFactorService(db)
        for item in items:
            symbol = (item.symbol or "").strip().upper()
            if not symbol:
                continue
            try:
                ohlcv = await _fetch_ohlcv(symbol)
                if not ohlcv or len(ohlcv) < 2:
                    stats["skipped"] += 1
                    continue
                panel = _build_panel(ohlcv)
                best = max(active, key=lambda x: x.get("confidence") or 0)
                spec = best["spec"]
                advise = await factor_service.advise_for_trade(
                    symbol=symbol, panel=panel, side="auto", top=10,
                    factor_ids=(spec.get("factor_ids") or None),
                )
                strategy = advise.get("strategy") or {}
                direction = advise.get("recommended_direction")
                confidence = float(strategy.get("confidence") or 0.0)
                min_conf = float(spec.get("min_confidence", s.min_confidence * 100))
                if not direction or direction == "neutral" or confidence * 100 < min_conf:
                    stats["skipped"] += 1
                    continue
                side = "long" if direction == "long" else "short"
                tip = SignalTip(
                    device_id=dev, source_id=source.id, slug=f"suite-{symbol}-{side.lower()}",
                    symbol=symbol, side=side, timeframe=settings.FACTOR_TIMEFRAME,
                    confidence=confidence,
                    rationale=f"Strategy '{best['name']}' (conf {confidence:.0%}, target {min_conf:.0f}%)",
                    text=f"{side.upper()} {symbol} via strategy {best['name']}.",
                    execution_status="pending",
                )
                db.add(tip)
                await db.flush()
                result = await maybe_auto_execute(db, dev, tip)
                stats["evaluated"] += 1
                if result.get("success") or result.get("executed"):
                    stats["traded"] += 1
                else:
                    stats["skipped"] += 1
                stats["details"].append({
                    "symbol": symbol, "strategy": best["name"],
                    "confidence": round(confidence, 3),
                    "result": result.get("success") or result.get("skipped") or result.get("error"),
                })
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("suite cycle symbol failed", device=dev, symbol=symbol, error=str(exc))
                stats["skipped"] += 1
    return stats

    async def status(self, device_id: str) -> Dict[str, Any]:
        strategies = await self.list_strategies(device_id)
        active = [s for s in strategies if s["status"] == "active"]
        return {
            "device_id": device_id,
            "total": len(strategies),
            "active": len(active),
            "active_strategies": [s["name"] for s in active],
            "strategies": strategies,
        }

    def _row_dict(self, r: StrategyRecord) -> Dict[str, Any]:
        return {
            "id": r.id,
            "device_id": r.device_id,
            "name": r.name,
            "spec": json.loads(r.spec) if r.spec else {},
            "status": r.status,
            "backtest": json.loads(r.backtest) if r.backtest else None,
            "confidence": r.confidence,
            "hit_rate": r.hit_rate,
            "sample_size": r.sample_size,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
