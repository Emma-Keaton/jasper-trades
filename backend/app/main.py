"""
Jasper Trades - Superpowered AI Trader
Main FastAPI Application
"""
import logging
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import List
import structlog

# Load .env file BEFORE any imports that use os.getenv()
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars only

from app.config import settings
from app.database import get_db, init_db, close_db, async_session
from app.models import Trade, Signal, Portfolio
from app.agents import DirectorAgent, QuantAgent, RiskAgent, ExecutionAgent, agent_registry
from app.services.llm_service import groq_client
from app.brokers import broker_registry, initialize_brokers
from app.services import init_scheduler, get_scheduler
from app.services.market_data_service import market_data_service
from app.services.forex_polling_service import start_forex_polling, stop_forex_polling
from app import device_identity
from app.services.boot import (
    DEPS_TASK,
    STARTUP_STEP_TIMEOUT_SECONDS,
    WARMUP_TASK,
    log_boot,
    run_boot_step,
    run_warmup,
    shutdown_step,
    start_deferred_deps,
    stop_deferred_deps,
    stop_warmup,
)

# Import API routes
from app.api.v1 import trading, agents, signals, portfolio, health, system, learning, risk, circuit_breaker
from app.api.v1 import market_intelligence
from app.api.v1 import chat
from app.api.websocket import streams as websocket_streams
from app.api.v1 import settings as api_settings_router
from app.api.v1 import alpha_factors, backtest, withdrawal, symbols
from app.api.v1 import heartbeat, polymarket, debate, ensemble, swarm, quantlib, checkpoint, notify
from app.api.v1 import trading_caps
from app.api.v1 import settings_extensions
from app.api.v1 import crypto_connector
from app.api.v1 import telegram_settings
from app.api.v1 import telegram_webhook
from app.api.v1 import telegram_chat
from app.api.v1 import telegram_bot_data
from app.api.v1 import broker_connections
from app.api.v1 import signal_sources
from app.api.v1 import forex  # Trove forex conversion
from app.api.v1 import banks  # Nigerian bank list
from app.api.v1 import trove  # Trove stocks (Nigerian/US stocks)
from app.api.v1 import akshare  # AKShare Chinese stocks
from app.api.v1 import akshare_settings  # AKShare settings
from app.api.v1 import dex_chains
from app.api.v1 import tiger  # Tiger OpenAPI live CN/US stocks
from app.api.v1 import exchanges
from app.api.v1 import geo  # geo-availability probe (Nigeria-safe sources)
from app.api.v1 import paper_trading  # Universal Paper Trading engine
from app.api.v1 import memecoin  # Solana memecoin discovery (DexScreener)
from app.api.v1 import market_data  # Unified market-data router (trending/prices/providers)
from app.api.v1 import watchlist  # Per-device durable symbol watchlist
from app.api.v1 import factor_trading  # Factor-sweep results (traded + watching)
from app.api.v1 import kronos  # Kronos forecast service proxy

# cTrader OAuth token refresh scheduler
try:
    from app.schedulers.ctrader_token_refresh import start_token_refresh_scheduler
    CTRADER_SCHEDULER_AVAILABLE = True
except ImportError:
    CTRADER_SCHEDULER_AVAILABLE = False

# Configure structured logging (compatible with latest structlog)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(colors=True) if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO if settings.DEBUG else logging.WARNING),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Log scheduler availability after logger is defined
if not CTRADER_SCHEDULER_AVAILABLE:
    logger.warning("cTrader token refresh scheduler not available")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Split into three phases, in this order deliberately:

    1. **Required** - database schema, agent registration, broker registry.
       Runs before the app serves anything. If the database is unreachable the
       process cannot serve honestly, so this fails fast.
    2. **Yield** - the app starts accepting requests. This is the point: a cold
       Render free-tier container now answers its health check.
    3. **Warm-up** - WebSockets, polling bots, Telegram listeners, background
       schedulers, optional-dependency status. Runs in the background, each step
       individually bounded and failure-isolated, so a slow or unreachable
       third-party API delays only itself and never blocks serving.
    """
    global WARMUP_TASK
    logger.info("Starting up Jasper Trades...")

    # -- 1. Required --------------------------------------------------------
    await run_boot_step("database", init_db, required=True)

    async def register_agents():
        director = DirectorAgent()
        quant = QuantAgent()
        risk = RiskAgent()
        execution = ExecutionAgent()

        agent_registry.register(director)
        agent_registry.register(quant)
        agent_registry.register(risk)
        agent_registry.register(execution)
        return list(agent_registry._agents.keys())

    names = await run_boot_step("agents", register_agents, required=True)
    logger.info("Agents initialized", agents=names)

    # Mark agents active. Without this every agent reported `is_active: false`
    # for the process lifetime, so the status endpoint told the UI that nothing
    # was running. Isolated per agent: one failing to start must not leave the
    # rest inactive.
    started = await run_boot_step("agents-start", agent_registry.start_all, required=False)
    if started:
        inactive = [name for name, ok in started.items() if not ok]
        if inactive:
            logger.warning("Some agents did not start", agents=inactive)

    async def connect_brokers():
        initialize_brokers()
        return await broker_registry.connect_all()

    await run_boot_step("brokers", connect_brokers, required=False)

    async def start_scheduler():
        scheduler = init_scheduler(async_session)
        await scheduler.start()
        return scheduler

    await run_boot_step("scheduler", start_scheduler, required=False)

    # -- 2. Serve -----------------------------------------------------------
    logger.info("Jasper Trades startup complete; accepting requests")

    # -- 3. Warm up in the background ---------------------------------------
    await run_warmup(
        [
            # First, and cheap: report which soft dependencies are absent so a
            # degraded capability is never silent. Install is not here - see
            # _start_deferred_deps for why it waits.
            ("optional-deps", _ensure_optional_deps),
            ("websocket-publishers", _start_websocket_publishers),
            ("default-portfolio", _create_default_portfolio),
            ("market-data", _start_market_data),
            ("telegram-bot", _start_telegram_bot),
            ("payout-scheduler", _start_payout_scheduler),
            ("ctrader-token-refresh", _start_ctrader_scheduler),
            ("forex-polling", start_forex_polling),
            ("telegram-listeners", _start_telegram_listeners),
            ("dexchain-watcher", _start_dexchain_watcher),
            ("signal-exits", _start_signal_exit_monitor),
        ]
    )

    # Started here, but it does no work yet: the task waits out a settle period and
    # a memory gate before installing anything, so in practice it begins once the
    # app is serving and boot has stopped competing for the 512 MB.
    if settings.OPTIONAL_DEPS_AUTO_INSTALL:
        start_deferred_deps(_install_optional_deps)

    try:
        yield
    finally:
        logger.info("Shutting down Jasper Trades...")

        # Every step runs unconditionally. Render sends SIGTERM then force-kills,
        # so skipping the remainder after one failure would leave the scheduler
        # running or the database open.
        await stop_deferred_deps()
        await stop_warmup()
        await shutdown_step("telegram-bot", _stop_telegram_bot)
        await shutdown_step("scheduler", _stop_scheduler)
        await shutdown_step("market-data", _stop_market_data)
        await shutdown_step("payout-scheduler", _stop_payout_scheduler)
        await shutdown_step("forex-polling", stop_forex_polling)
        await shutdown_step("telegram-listeners", _stop_telegram_listeners)
        await shutdown_step("agents", agent_registry.stop_all)
        await shutdown_step("brokers", broker_registry.disconnect_all)
        await shutdown_step("database", close_db)
        logger.info("Jasper Trades shutdown complete")


# ---------------------------------------------------------------------------
# Boot steps
#
# Each is a small module-level coroutine so `run_boot_step` can wrap it in a
# timeout, and so shutdown has symmetric counterparts. Keeping them out of the
# lifespan body is what makes that wrapping possible at all.
# ---------------------------------------------------------------------------

async def _ensure_optional_deps():
    """Report which soft dependencies are absent. Installs nothing.

    Logging only, because it runs as the first warm-up step while boot is still
    competing for memory. The install is _install_optional_deps below.
    """
    from app.services.optional_deps import ensure_optional_deps

    await ensure_optional_deps()


async def _install_optional_deps():
    """Settle, wait for memory headroom, then install the absent soft tier.

    Started as a cancellable background task and does nothing until the app is
    already serving and the process is small enough that a pip subprocess cannot
    provoke the OOM killer on a 512 MB instance.
    """
    from app.services.optional_deps import install_deferred

    await install_deferred()


async def _start_websocket_publishers():
    from app.api.websocket.streams import start_publisher_tasks

    await start_publisher_tasks()


async def _create_default_portfolio():
    """Seed a paper portfolio so a fresh database is immediately usable.

    The device UUID minted here is a *server-generated placeholder*, not a
    credential. It exists only so a brand-new database has a portfolio row and
    the UI is not empty. It is never returned to a client and never sent as a
    header, so it grants nobody access - the real device UUID comes from the
    browser via `crypto.randomUUID()`.

    It also cannot satisfy the `require_device_id` validation rule, so a request
    can never present it. A device presenting its own UUID creates its own
    portfolio on first use via `create_portfolio(device_id=...)`.
    """
    from app.services.portfolio_service import PortfolioService

    db = async_session()
    try:
        service = PortfolioService(db)
        if await service.get_portfolios():
            return None
        placeholder_device = device_identity.new_device_id()
        await service.create_portfolio(
            name="Default",
            initial_cash=settings.UNIVERSAL_PAPER_CAPITAL,
            is_paper=True,
            device_id=placeholder_device,
        )
        logger.info(
            "Seeded placeholder portfolio for a fresh database",
            device_id=placeholder_device[:8],
        )
        return None
    finally:
        await db.close()


async def _start_market_data():
    """Start price streams for the symbols the portfolio actually holds.

    On a free-tier instance the container is destroyed on every sleep, so these
    WebSockets are re-established on every wake. `market_data_service` owns its
    own backoff reconnect once started; this only has to get it going.
    """
    from app.services.portfolio_service import PortfolioService

    db = async_session()
    try:
        service = PortfolioService(db)
        portfolios = await service.get_portfolios()
        if not portfolios:
            return None
        positions = await service.get_all_positions(portfolios[0].id)
        symbols = [p.symbol for p in positions] if positions else ["AAPL", "NVDA", "SPY"]
        await market_data_service.start(symbols)

        crypto_symbols = [
            s
            for s in symbols
            if any(x in s.upper() for x in ["BTC", "ETH", "USDT", "USDC", "SOL", "BNB"])
        ]
        if crypto_symbols:
            from app.services.ccxt_watch_service import get_ccxt_watch_service

            await get_ccxt_watch_service().start(crypto_symbols)
        return len(symbols)
    finally:
        await db.close()


async def _start_telegram_bot():
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.info("Telegram bot disabled: TELEGRAM_BOT_TOKEN not set")
        return None
    from app.services.telegram_bot_service import (
        get_telegram_bot_service,
        is_polling_started,
        mark_polling_started,
    )

    if is_polling_started():
        logger.info("Telegram polling already active, skipping duplicate start")
        return None
    service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
    await service.initialize()
    asyncio.create_task(service.start_polling())
    mark_polling_started()
    return "polling"


async def _start_payout_scheduler():
    """Auto-payouts need both the flag and a production environment.

    Deliberately safe-by-default: with either missing, this logs why instead of
    starting, so an operator does not configure payouts and then see nothing
    happen with no explanation.
    """
    if not (settings.AUTO_PAYOUTS_ENABLED and _is_prod):
        logger.info(
            "Auto-payout scheduler not started "
            f"(AUTO_PAYOUTS_ENABLED={settings.AUTO_PAYOUTS_ENABLED}, "
            f"ENVIRONMENT={settings.ENVIRONMENT}; both required)"
        )
        return None
    from app.services.payout_scheduler import payout_scheduler

    await payout_scheduler.start()
    return "hourly"


async def _start_ctrader_scheduler():
    if not CTRADER_SCHEDULER_AVAILABLE:
        return None
    from app.database import async_engine

    await start_token_refresh_scheduler(async_engine)
    return "6h"


async def _start_dexchain_watcher():
    from app.services.dex_chain_autotrade import start_dexchain_watch

    asyncio.create_task(start_dexchain_watch())


async def _start_signal_exit_monitor():
    from app.services.signal_exits import start_signal_exit_monitor

    asyncio.create_task(start_signal_exit_monitor())


async def _start_telegram_listeners():
    from sqlalchemy import select as _select

    from app.models import TelegramAccount
    from app.services.signal_sources.telegram_listener import get_listener

    async with async_session() as db:
        result = await db.execute(_select(TelegramAccount))
        accounts = result.scalars().all()

    started = 0
    for account in accounts:
        if await get_listener().sync(account.device_id):
            started += 1
    logger.info(f"Telegram signal listeners started: {started}/{len(accounts)}")
    return started


# ---------------------------------------------------------------------------
# Shutdown counterparts
# ---------------------------------------------------------------------------

async def _stop_telegram_bot():
    from app.services.telegram_bot_service import telegram_bot_service

    if telegram_bot_service and telegram_bot_service.running:
        await telegram_bot_service.stop_polling()


async def _stop_scheduler():
    scheduler = get_scheduler()
    if scheduler:
        await scheduler.stop()


async def _stop_market_data():
    from app.services.ccxt_watch_service import get_ccxt_watch_service

    await market_data_service.stop()
    await get_ccxt_watch_service().stop()


async def _stop_payout_scheduler():
    from app.services.payout_scheduler import payout_scheduler

    await payout_scheduler.stop()


async def _stop_telegram_listeners():
    from app.services.signal_sources.telegram_listener import get_listener

    await get_listener().stop_all()


# Create FastAPI app
# Interactive API docs are a dev convenience; disable them in production so the
# attack surface isn't discoverable (OpenAPI schema stays internal-only).
_is_prod = settings.ENVIRONMENT == "production"
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Superpowered AI Trader - Merging Fincept, AI-Trader, Vibe-Trading, and AutoHedge",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# CRITICAL: Security validation on startup
def validate_security_config():
    """Validate critical security configuration."""
    errors = []
    warnings = []
    
    # 1. Check SECRET_KEY is not default
    is_production = settings.ENVIRONMENT == "production"
    if settings.SECRET_KEY == "change-this-in-production":
        msg = (
            "SECRET_KEY is set to default 'change-this-in-production'. "
            "This allows attackers to forge valid JWT tokens. "
            "Generate a strong key: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
        if is_production:
            errors.append("CRITICAL: " + msg)
        else:
            warnings.append("WARNING (dev): " + msg)
    
    if len(settings.SECRET_KEY) < 32:
        msg = (
            f"SECRET_KEY is too short ({len(settings.SECRET_KEY)} chars). "
            "Must be at least 32 characters for security. "
            "Generate: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
        if is_production:
            errors.append("CRITICAL: " + msg)
        else:
            warnings.append("WARNING (dev): " + msg)
    
    # 2. Check CORS configuration
    if "*" in settings.cors_origins_list:
        if settings.CORS_ALLOW_CREDENTIALS:
            errors.append(
                "SECURITY: CORS is configured with wildcard origins (*) AND allow_credentials=True. "
                "This allows cross-origin requests with credentials, enabling CSRF-like attacks. "
                "Either: (a) Use specific origins, or (b) Set allow_credentials=False"
            )
        else:
            warnings.append(
                "WARNING: CORS allows wildcard origins (*). This is generally permissive. "
                "Consider restricting to specific frontend URLs."
            )
    
    # 3. Environment validation
    if settings.ENVIRONMENT == "production":
        if settings.DEBUG:
            errors.append("SECURITY: DEBUG=true in production. This exposes sensitive information.")
        
        if not settings.using_postgres:
            warnings.append(
                "WARNING: Production environment but using SQLite database. "
                "Recommended: Use PostgreSQL/Supabase for production deployments."
            )
    
    # Log errors and exit
    if errors:
        for error in errors:
            logger.error(error)
        raise RuntimeError(f"Security validation failed with {len(errors)} critical issue(s). See logs above.")
    
    # Log warnings
    for warning in warnings:
        logger.warning(warning)

# Run security validation
validate_security_config()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (Production security)
try:
    from app.middleware.rate_limiter import RateLimitMiddleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        burst=settings.RATE_LIMIT_BURST,
        enabled=settings.RATE_LIMIT_ENABLED,
    )
    logger.info("Rate limiting middleware enabled")
except Exception as e:
    logger.warning(f"Rate limiting middleware not available: {e}")

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(market_intelligence.router, prefix="/api/v1", tags=["market-intelligence"])
app.include_router(trading.router, prefix="/api/v1/trading", tags=["trading"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(signal_sources.router, prefix="/api/v1", tags=["signals"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
app.include_router(learning.router, prefix="/api/v1", tags=["self-learning"])
app.include_router(api_settings_router.router, tags=["settings"])
app.include_router(withdrawal.router, prefix="/api/v1", tags=["withdrawal"])
app.include_router(circuit_breaker.router, prefix="/api/v1", tags=["circuit-breaker"])
app.include_router(telegram_settings.router, prefix="/api/v1", tags=["telegram-settings"])
app.include_router(telegram_webhook.router, tags=["telegram-webhook"])
app.include_router(telegram_chat.router, prefix="/api/v1", tags=["telegram-chat"])
app.include_router(telegram_bot_data.router, tags=["telegram-bot-data"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(alpha_factors.router, prefix="/api/v1/alpha-factors", tags=["alpha-factors"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
app.include_router(websocket_streams.router, tags=["websocket"])
app.include_router(heartbeat.router, tags=["heartbeat"])
app.include_router(polymarket.router, tags=["polymarket"])
app.include_router(debate.router, tags=["structured-debate"])
app.include_router(ensemble.router, tags=["ensemble"])
app.include_router(swarm.router, tags=["swarm"])
app.include_router(quantlib.router, tags=["quantlib"])
app.include_router(checkpoint.router, tags=["checkpoint"])
app.include_router(notify.router, tags=["notify"])
app.include_router(trading_caps.router, prefix="/api/v1", tags=["trading-caps"])
app.include_router(settings_extensions.router, prefix="/api/v1", tags=["settings-extensions"])
app.include_router(exchanges.router, prefix="/api/v1", tags=["exchanges"])
app.include_router(crypto_connector.router, prefix="/api/v1", tags=["crypto-connector"])
app.include_router(broker_connections.router, prefix="/api/v1", tags=["brokers"])
app.include_router(forex.router, tags=["forex"])  # Trove forex conversion
app.include_router(banks.router, prefix="/api/v1", tags=["banks"])  # Nigerian bank list
app.include_router(symbols.router, prefix="/api/v1", tags=["symbols"])  # Symbol listing (US + NGX)
app.include_router(trove.router, prefix="/api/v1", tags=["trove"])  # Trove trading (Nigerian/US stocks)
app.include_router(akshare.router, prefix="/api/v1", tags=["akshare"])  # AKShare Chinese stocks
app.include_router(akshare_settings.router, tags=["akshare-settings"])  # AKShare settings
app.include_router(tiger.router, prefix="/api/v1", tags=["tiger"])  # Tiger OpenAPI (live CN/US)
app.include_router(geo.router, prefix="/api/v1", tags=["geo"])  # geo-availability
app.include_router(paper_trading.router, prefix="/api/v1", tags=["paper-trading"])  # paper engine
app.include_router(memecoin.router, prefix="/api/v1", tags=["memecoin"])  # Solana memecoins
app.include_router(dex_chains.router, prefix="/api/v1", tags=["dex-chains"])  # Dex chain watchers
app.include_router(market_data.router, prefix="/api/v1", tags=["market-data"])  # unified market data
app.include_router(watchlist.router, prefix="/api/v1", tags=["watchlist"])  # durable watchlist
app.include_router(factor_trading.router, prefix="/api/v1", tags=["factor-trading"])
app.include_router(kronos.router, prefix="/api/v1", tags=["kronos"])  # factor results


@app.get("/")
async def root():
    """Root endpoint."""
    scheduler = get_scheduler()
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "scheduler_running": scheduler._running if scheduler else False,
    }


# In production the interactive docs are disabled; expose a neutral root response.
if _is_prod:
    @app.get("/docs")
    @app.get("/redoc")
    @app.get("/openapi.json")
    async def _docs_disabled():
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
        )


@app.get("/api/v1/status")
async def status():
    """System status."""
    scheduler = get_scheduler()

    return {
        "status": "healthy",
        "agents": list(agent_registry._agents.keys()),
        "active_agents": len(agent_registry.get_active()),
        "brokers": broker_registry.list_brokers(),
        "broker_status": broker_registry.get_stats(),
        "scheduler": scheduler.get_status() if scheduler else {"running": False},
    }


@app.get("/api/v1/system/tasks")
async def get_system_tasks():
    """Get background task status."""
    scheduler = get_scheduler()

    if not scheduler:
        return {"error": "Scheduler not initialized"}

    return scheduler.get_status()


# Serve frontend static files in production (Render monorepo deployment)
# This serves the Next.js built files from backend/static
import os
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists() and (static_dir / "index.html").exists():
    logger.info("Frontend build detected - serving static files")
    
    # Serve static assets
    app.mount("/_next/static", StaticFiles(directory=str(static_dir / "_next" / "static")), name="next_static")
    
    # Serve public assets
    public_dir = static_dir / "public"
    if public_dir.exists():
        app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")
    
    # Catch-all route for Next.js pages (SPA routing)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve Next.js frontend with proper routing support"""
        # Don't serve API routes through frontend
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404)
        
        # Try to serve from _next/static first
        if full_path.startswith("_next/static/"):
            file_path = static_dir / "_next" / "static" / full_path.replace("_next/static/", "")
            if file_path.exists():
                return FileResponse(str(file_path))
        
        # Try public assets
        public_file = public_dir / full_path
        if public_file.exists():
            return FileResponse(str(public_file))
        
        # Serve index.html for all other routes (Next.js client-side routing)
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        
        return HTMLResponse(content="Frontend not built. Run: npm run build in frontend/", status_code=404)
else:
    logger.info("No frontend build detected - API-only mode")
    @app.get("/app")
    async def app_root():
        """Root endpoint when frontend not available"""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "API-only mode (frontend not built)",
            "docs": "/docs",
        }

