# Signal Pipeline & Deployment — Implementation Plan

Status: **Approved / Ready to implement**
Order: Parts 1 → 7. Verify after each part; full test pass in Part 7.

---

## Part 1 — Model env config (Gemini main + NVIDIA fallback)

Goal: task→model routing is env-configurable for BOTH providers.

Files:
- `backend/app/config.py` — add:
  - `NVIDIA_MODEL_FAST: str = "nvidia/nemotron-mini-4b-instruct"`
  - `NVIDIA_MODEL_BALANCED: str = "nvidia/llama-3.1-8b-instruct"`
  - `NVIDIA_MODEL_SMART: str = "nvidia/llama-3.1-8b-instruct"`
  - `NVIDIA_MODEL_DEEP: str = "nvidia/llama-3.3-nemotron-super-49b-v1"`
  - `NVIDIA_MODEL_ALT: str = "openai/gpt-oss-20b"`
  - `COINMARKETCAP_API_KEY: Optional[str] = None`
  - `RAYDIUM_API_BASE: str = "https://api-v3.raydium.io"`
- `backend/app/nvidia_nim.py` — `_get_model_for_task` (L49-61) reads the `NVIDIA_MODEL_*` settings (mirrors `llm_service.py:189-202` Gemini routing).
- `backend/.env.render` — add the 3 missing Gemini keys + 5 NVIDIA keys + `COINMARKETCAP_API_KEY` line.

Render env block (paste into Render):
```
GEMINI_API_KEYS=key1,key2,...
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL_FAST=gemini-2.5-flash-lite
MODEL_FREE_FAST=gemini-2.5-flash-lite
MODEL_BALANCED=gemini-2.5-flash
MODEL_SMART=gemini-2.5-flash
MODEL_SMART_FREE=gemini-2.5-flash
MODEL_DEEP=gemini-2.5-pro
MODEL_ALTERNATIVE=gemini-2.5-flash
NVIDIA_MODEL_FAST=nvidia/nemotron-mini-4b-instruct
NVIDIA_MODEL_BALANCED=nvidia/llama-3.1-8b-instruct
NVIDIA_MODEL_SMART=nvidia/llama-3.1-8b-instruct
NVIDIA_MODEL_DEEP=nvidia/llama-3.3-nemotron-super-49b-v1
NVIDIA_MODEL_ALT=openai/gpt-oss-20b
COINMARKETCAP_API_KEY=<your key>
```

Verify: `python -c "from app.config import settings; print(settings.NVIDIA_MODEL_DEEP)"`; boot app, hit `/api/v1/settings/env-status`, confirm NVIDIA models configurable.

---

## Part 2 — Trade execution through all routes (paper + live)

Goal: every execution path works in paper AND live; Home/Trades reflect activity.

- **Paper ledger → real Portfolio**: `backend/app/services/paper_trading_service.py::place_trade` (L171-188) currently writes only JSON state + bare `Trade` rows. Add: create/update `Position` rows and debit `Portfolio.cash` on buys / credit on sells (via `PortfolioService.add_position/update_cash`), keyed to the device's default portfolio. Keep the JSON ledger as source of truth for paper.
- **Fix 404s breaking Home**:
  - Add `GET /api/v1/portfolio/{portfolio_id}` summary route in `backend/app/api/v1/portfolio.py` (page.tsx L137 + api-client.ts L161 call it).
  - Add `GET /api/v1/portfolio/{portfolio_id}/trades` route returning recent `Trade` rows in the shape `page.tsx:120,149` parses (`type`=BUY/SELL, `symbol`, `shares`, `price`, `total`, `created_at`). (Or repoint frontend to `/api/v1/trading/history`.)
  - Resolve `GET /api/v1/portfolio` array-vs-dict mismatch (page.tsx:104 treats it as array; portfolio.py returns a dict). Return the list `[summary]` or fix frontend to read `.data[0]`/summary.
- **Paper device scoping**: `paper_trading_service.py` `_load_state`/`_save_state` (L74, L89) use `select(DeviceSettings).limit(1)` — filter `where(device_id == device_id)` and upsert per device.
- **Frontend dead calls**: `useExecuteTrade` (`hooks/use-api.ts:87`) → repoint to real route or remove; `DELETE /api/v1/trading/{tradeId}/cancel` (api-client.ts:198) → add backend route or remove; `/api/v1/signals/active`, `/signals/{id}/ack|execute` (api-client.ts:211-217) → repoint to `/signals/tips/...` or remove.

Verify: paper buy via `/api/v1/paper/trade` → `Position` created + `Portfolio.cash` decreased + `Trade` row; Home polls now show cash/holdings/trades.

---

## Part 3 — Preflight prerequisites check (paper|live)

Goal: no route silently no-ops; missing prereqs return a checklist with next steps.

- New `backend/app/api/v1/system.py` endpoint: `GET /api/v1/system/setup-status` →
  ```
  { ready: bool, missing: [{key, label, ok, message, next_step}],
    items: { llm_ready, watchlist_count, signal_sources_count, portfolio_funded, paper_enabled, market_data_ready } }
  ```
  - llm_ready = GEMINI_API_KEYS or NVIDIA_API_KEY configured.
  - watchlist_count / signal_sources_count from DB per X-Device-ID.
  - portfolio_funded = default portfolio cash > 0.
  - paper_enabled = settings.UNIVERSAL_PAPER_TRADING.
  - market_data_ready = ValuationService can resolve a price.
- New `backend/app/services/preflight.py` with async `run_preflight(db, device_id, mode)` returning the checklist; raise a typed `PreflightError(status=400, detail={...})`.
- Wire into every execution route: `trading.py::execute_trade`, `paper_trading.py::place`, `signal_sources.py::POST /signals/tips/{id}/execute`, `ingest.py::maybe_auto_execute/execute_signal`, `trove.py::order`, `akshare.py::order`. When `missing` → HTTP 400 with `{error, missing, next_step}`.
- Frontend: HomeScreen shows the "Setup needed" card (list missing items + CTA nav to Settings/Signals) whenever `running` and `setup-status.ready == false`. (Also populates the guidance in Part 2 empty states.) Non-zero + non-empty states now also have direction.

Verify: with no keys/watchlist, `POST /api/v1/paper/trade` → 400 listing `llm_ready`, `watchlist_count`; after adding keys/watchlist → succeeds.

---

## Part 4 — Watchlist (two signal inputs + Telegram gate)

Goal: user-defined symbols are watched/priced/traded; Telegram & watchlist are the two signal inputs.

Backend:
- `backend/app/models.py`: `WatchlistItem` (device_id, symbol, name, asset_class, enabled, created_at; `UNIQUE(device_id, symbol)`). Add to `create_all`.
- New `backend/app/api/v1/watchlist.py` (mount `/api/v1`, tags `watchlist`):
  - `GET /api/v1/watchlist` → list for X-Device-ID (with optional live `price`, `change_24h`).
  - `POST /api/v1/watchlist` body `{symbol, name?, asset_class?}` → auto-detect asset class, add.
  - `POST /api/v1/watchlist/batch` body `{symbols: [{symbol, ...}]}`.
  - `DELETE /api/v1/watchlist/{id}`; `PATCH /api/v1/watchlist/{id}` `{enabled}`.
  - `GET /api/v1/watchlist/prices` → live prices via ValuationService.
- **Scheduler** `backend/app/services/scheduler.py` `_generate_signals` (L196-217, currently stub): per enabled watchlist item per device —
  1. fetch price (ValuationService) + price history (CCXT `get_ohlcv` for crypto, Yahoo `data_connectors.get_yfinance_data` for stocks),
  2. compute momentum/confidence (deterministic: return over N bars, volatility → z-score → confidence 0-1; upgrade to Kronos/Gemini via existing `confidence.py`/`llm` when configured),
  3. emit `SignalTip` (side from momentum sign, confidence), queue through `maybe_auto_execute` (paper default).
  Run every `settings.SIGNAL_GEN_INTERVAL` (default 300s), one batch per source symbol.
- **Telegram gate**: add `only_trade_watchlist: bool = True` to `SignalSettings` (or store in `SignalSettings` row). In `ingest.py::maybe_auto_execute` (L156-167): if `only_trade_watchlist` and tip symbol not in device's watchlist → `_mark(tip, "skipped", "not in watchlist")`. Add to `GET/POST /api/v1/signals/settings`.
- `backend/app/services/signal_sources/ingest.py::_asset_class` — extend the crypto set to pull from watchlist when present.

Frontend:
- `MarketsScreen.tsx`: add "My watchlist" section — add-symbol input (comma separated, quick-add suggestions from `/api/v1/symbols` + `/api/v1/memecoin/search` + CCXT symbols), live prices, remove/disable toggle, star icons (`data-onboarding="watchlist-star"`). Show **Trending** group (Part 5) separate from **Watchlist**.
- `HomeScreen.tsx`: `watching` (L50-53) reads real watchlist symbols instead of `DEFAULT_WATCHING`; still caps at 6.
- `SignalsScreen.tsx` / Settings: toggle "Only trade watchlist symbols".

Verify: add `BTC,SOL,AAPL` via API → scheduler generates tips after interval → paper trades fill via Part 2 wiring; Telegram tip for off-watchlist symbol is skipped when gate ON, executes when OFF.

---

## Part 5 — Market-data expansion + trending groups

Goal: CoinMarketCap, CoinGecko, Trove, AkShare, Raydium feed market data; Trending is grouped separately from watchlist; market-intelligence folded in.

- New `backend/app/api/v1/market_data.py` router (mount `/api/v1/market-data`):
  - `GET /api/v1/market-data/trending?limit=12` → `{coins: [{symbol, name, change, price, source}]}` aggregated:
    - CoinGecko `/search/trending` (reuse `market_data_providers.get_trending_coins_coingecko` L134-159),
    - CoinMarketCap (if `COINMARKETCAP_API_KEY`) trending/gainers via `/v1/cryptocurrency/trending/gainers-losers` or listings `quote=USD`,
    - Trove popular stocks (`TroveSymbol` list),
    - AkShare `stock_zh_a_spot_em` top movers (China A),
    - dedupe by symbol, keep `source`.
  - `GET /api/v1/market-data/prices` body `{symbols:[]}` → batch prices via ValuationService.
  - `GET /api/v1/market-data/watchlist-prices` → same as watchlist/prices.
  - Route **grouping**: `source: "trending"` vs `"watchlist"` so frontend can render two groups.
- **Provider chain** `backend/app/services/market_data_router.py`: add CoinMarketCap client between CoinGecko and CCXT; fallback chain CoinGecko → CMC → CCXT → CoinLore.
- **Stock + forex pricing fix** `backend/app/services/valuation_service.py`:
  - `_fetch_stock_price` (L181-212) has `broker = None` hardcoded → route through Trove quote (`trove.py` `/quote/{symbol}`) then Yahoo (`data_connectors.get_yfinance_data`) then AkShare.
  - Forex: add asset-class detection + price via existing `market_data_providers.get_currency_conversion` / forex router static rates.
- **Memecoin = Raydium + CoinMarketCap**: `backend/app/services/solana_memecoin_service.py` — add `RAYDIUM_API_BASE` client (`/main/pools` / pool info for price + volume, keyless) alongside DexScreener; CMC trending for memecoin when key present. Add route `GET /api/v1/memecoin/discover?limit=8` (frontend `MarketsScreen.tsx:34` calls it today → 404) as alias for trending.
- **Market-intelligence fix**: `backend/app/services/agent_reach/market_intel_service.py` is a 2-method STUB — `get_trending_stocks`, `search_news`, `health_check`, `_fetch_all_news` 500 (market_intelligence.py L112/L156/L189/L226). Implement on `MarketIntelService` using existing `signal_sources` scrapers (rss/reddit/stocktwits/telegram) + `SentimentAnalysisService`; endpoints keep working.
- Frontend `MarketsScreen.tsx`: call real `/api/v1/market-data/trending` + `/api/v1/memecoin/discover`; render "Trending" and "My watchlist" as separate groups.

Verify: `/api/v1/market-data/trending` returns non-empty coins; `/api/v1/memecoin/discover` 200; market-intel `/trending` no longer 500s; ValuationService returns a price for `AAPL` and `EURUSD`.

---

## Part 6 — Onboarding persistence (per-page, DB, reset only via Settings)

Goal: per-page completion persists in DB and resurfaces only after explicit reset.

Verified current state: `completed_tours`, `onboarding_completed`, `welcome_done` live in `device_settings.preferences` JSON, keyed by `X-Device-ID`, via `POST/GET /api/v1/settings/preferences` (`settings_extensions.py:448-510`). Per-page already functions (engine restores + `markTourComplete` persists; `OnboardingTour` auto-start skips completed).

Fixes:
- `frontend/components/onboarding/useOnboardingEngine.ts::resetTours()` (L207-213): **also clear `welcome_done`** so WelcomeWizard reappears after reset.
- Reset button stays the only reset path: `components/SettingsTab.tsx:1176-1186` ("Reset Onboarding Tours" → `resetTours()` → DB write). Ensure nothing else calls `resetTours()` or clears prefs.
- `frontend/components/onboarding/OnboardingTour.tsx` `TOUR_MAP` (L22-41): add `backtest` step + `alphazoo` step (or explicitly exclude both — no tour for them), so nav to a tour-bearing page honors persistence.
- Consolidate: delete or alias orphaned `frontend/components/onboarding/tours/*.ts` (dashboard/settings/signals/portfolio/backtest/alphazoo/agents — zero imports) so the live inline `TOUR_MAP` is the single source of truth; remove the misleading "restart anytime from Help menu" string in `InteractiveTooltip.tsx:104` (no Help menu exists).

Verify: complete Home tour → refresh → no Home tour; reset in Settings → Home tour + wizard show again; no other path clears tours.

---

## Part 7 — Test all workflows

Automated + manual smoke:

Backend (pytest + httpx ASGI):
- Model routing: Gemini primary; forces fallback to NVIDIA on simulated Gemini 429; env overrides respected.
- Every execution route paper AND live: `/api/v1/trading/execute`, `/api/v1/paper/trade`, `/api/v1/signals/tips/{id}/execute`, `/api/v1/signals/fetch` (auto), `trove/order`, `akshare/order`. Assert Position/Portfolio.cash/Trade consistency for paper.
- Preflight: each route with missing prereqs → 400 + `missing[]`; with full config → 200/executed.
- Watchlist: CRUD, batch, prices; scheduler generates tips (mock interval/time); Telegram gate ON skips off-watchlist tips, OFF executes.
- Market data: `/market-data/trending` shape; provider failover (kill CoinGecko → CMC → CCXT); `/memecoin/discover`; market-intel no 500; stock + forex prices resolve.
- Onboarding: prefs round-trip; reset clears `welcome_done`.

Frontend (Playwright/browser):
- Home: cash/holdings/trades render from real backend; Start with missing prereqs shows Setup-Needed card + CTAs.
- Markets: Trending + My watchlist groups render; add/remove star.
- Signals: gate toggle ON skips off-watchlist tips (UI reflects skip reason).
- Settings: reset re-shows tours + wizard; completed pages don't re-tour.
- Start→trade: paper trade appears in Home stats + Trades within poll interval.

Env integration (live server on 8099, DEBUG=false, Supabase DATABASE_URL):
- Re-running full smoke against Supabase (health, settings, sources, tips, status) — same as bootstrap smoke, now incl. all new endpoints.

---

## Deploy notes (post-implementation)

- Render backend: paste env block from Part 1 + Supabase `DATABASE_URL` (pooler 6543), `CORS_ORIGINS`/`NEXT_PUBLIC_*`, `SECRET_KEY`/`API_AUTH_KEY`, `TELEGRAM_API_ID/HASH`, `BACKEND_INTERNAL_URL`.
- Vercel frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, feature flags (no Supabase vars).
- Commit each Part as green; final commit + push when approved.