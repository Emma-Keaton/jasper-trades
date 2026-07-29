"""
Jasper Trades - Superpowered AI Trader
Main FastAPI Application
"""
import logging
import asyncio
import uuid
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
from app.nvidia_nim import nvidia_client
from app.brokers import broker_registry, initialize_brokers
from app.services import init_scheduler, get_scheduler
from app.services.market_data_service import market_data_service
from app.services.forex_polling_service import start_forex_polling, stop_forex_polling

# Kronos integration (optional - 4GB RAM optimized)
try:
    from app.services.kronos import set_memory_limits, configure_torch_cpu
    KRONOS_AVAILABLE = True
except ImportError:
    KRONOS_AVAILABLE = False
    set_memory_limits = lambda **kwargs: None  # type: ignore
    configure_torch_cpu = lambda: None  # type: ignore

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
from app.api.v1 import copytrade
from app.api.v1 import forex  # Trove forex conversion
from app.api.v1 import banks  # Nigerian bank list
from app.api.v1 import trove  # Trove stocks (Nigerian/US stocks)
from app.api.v1 import akshare  # AKShare Chinese stocks
from app.api.v1 import akshare_settings  # AKShare settings
from app.api.v1 import exchanges

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
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up Jasper Trades...")

    # Configure for 4GB RAM systems
    set_memory_limits(max_ram_mb=2048)  # Limit to 2GB for safety
    configure_torch_cpu()
    logger.info("Configured memory limits for 4GB RAM system")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize agents
    director = DirectorAgent()
    quant = QuantAgent()
    risk = RiskAgent()
    execution = ExecutionAgent()

    agent_registry.register(director)
    agent_registry.register(quant)
    agent_registry.register(risk)
    agent_registry.register(execution)

    logger.info("Agents initialized", agents=list(agent_registry._agents.keys()))

    # Initialize brokers
    try:
        initialize_brokers()
        broker_results = await broker_registry.connect_all()
        logger.info("Brokers initialized", results=broker_results)
    except Exception as e:
        logger.warning(f"Broker initialization failed (will retry on first trade): {e}")

    # Initialize scheduler (background tasks)
    scheduler = init_scheduler(async_session)
    await scheduler.start()
    logger.info("Scheduler started")

    # Create default portfolio if none exists
    try:
        from app.services.portfolio_service import PortfolioService
        db = async_session()
        portfolio_service = PortfolioService(db)

        portfolios = await portfolio_service.get_portfolios()
        if not portfolios:
            # Generate a device ID for the default portfolio
            device_id = str(uuid.uuid4())
            await portfolio_service.create_portfolio(
                name="Default",
                initial_cash=100000.0,
                is_paper=True,
                device_id=device_id,
            )
            logger.info(f"Created default portfolio for device {device_id[:8]}...")

        await db.close()
    except Exception as e:
        logger.warning(f"Could not create default portfolio: {e}")

    logger.info("Jasper Trades startup complete")

    # Start market data WebSocket (real-time prices)
    try:
        # Get symbols from default portfolio
        from app.services.portfolio_service import PortfolioService
        db = async_session()
        portfolio_service = PortfolioService(db)
        portfolios = await portfolio_service.get_portfolios()
        
        if portfolios:
            positions = await portfolio_service.get_all_positions(portfolios[0].id)
            symbols = [p.symbol for p in positions] if positions else ["AAPL", "NVDA", "SPY"]
            await market_data_service.start(symbols)
            logger.info(f"Market data started with {len(symbols)} symbols")
        
        await db.close()
    except Exception as e:
        logger.warning(f"Market data service startup failed: {e}")

    # Start Telegram Bot (Notifications + 2-Way Chat)
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            from app.services.telegram_bot_service import get_telegram_bot_service
            bot_service = get_telegram_bot_service(settings.TELEGRAM_BOT_TOKEN)
            await bot_service.initialize()
            
            # Start polling in background (for local dev)
            asyncio.create_task(bot_service.start_polling())
            logger.info("Telegram Bot started (long polling mode)")
        except Exception as e:
            logger.warning(f"Telegram Bot startup failed: {e}")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set - Telegram bot disabled")

    # Start auto-payout scheduler
    try:
        from app.services.payout_scheduler import payout_scheduler
        await payout_scheduler.start()
        logger.info("Auto-payout scheduler started (checks every hour)")
    except Exception as e:
        logger.warning(f"Auto-payout scheduler startup failed: {e}")

    # Start cTrader OAuth token refresh scheduler (refreshes tokens every 6 hours)
    if CTRADER_SCHEDULER_AVAILABLE:
        try:
            from app.database import async_engine
            await start_token_refresh_scheduler(async_engine)
            logger.info("cTrader token refresh scheduler started (refreshes every 6 hours)")
        except Exception as e:
            logger.warning(f"cTrader token refresh scheduler startup failed: {e}")

    # Start forex polling service (NGN/USD rates every 60 seconds)
    try:
        await start_forex_polling()
        logger.info("Forex polling service started (NGN/USD rates every 60s)")
    except Exception as e:
        logger.warning(f"Forex polling service startup failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Jasper Trades...")

    # Stop Telegram Bot
    try:
        from app.services.telegram_bot_service import telegram_bot_service
        if telegram_bot_service and telegram_bot_service.running:
            await telegram_bot_service.stop_polling()
            logger.info("Telegram Bot stopped")
    except Exception as e:
        logger.warning(f"Error stopping Telegram Bot: {e}")

    # Stop scheduler
    if get_scheduler():
        await get_scheduler().stop()
        logger.info("Scheduler stopped")

    # Stop market data
    await market_data_service.stop()
    logger.info("Market data service stopped")

    # Stop payout scheduler
    try:
        from app.services.payout_scheduler import payout_scheduler
        await payout_scheduler.stop()
        logger.info("Auto-payout scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping payout scheduler: {e}")

    # Stop forex polling service
    try:
        await stop_forex_polling()
        logger.info("Forex polling service stopped")
    except Exception as e:
        logger.warning(f"Error stopping forex polling: {e}")

    # Stop agents
    await agent_registry.stop_all()
    logger.info("Agents stopped")

    # Disconnect brokers
    await broker_registry.disconnect_all()
    logger.info("Brokers disconnected")

    # Close database
    await close_db()
    logger.info("Database closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Superpowered AI Trader - Merging Fincept, AI-Trader, Vibe-Trading, and AutoHedge",
    lifespan=lifespan,
)

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
app.include_router(broker_connections.router, prefix="/api/v1", tags=["brokers"])
app.include_router(copytrade.router, tags=["Copy Trading"])
app.include_router(forex.router, tags=["forex"])  # Trove forex conversion
app.include_router(banks.router, prefix="/api/v1", tags=["banks"])  # Nigerian bank list
app.include_router(symbols.router, prefix="/api/v1", tags=["symbols"])  # Symbol listing (US + NGX)
app.include_router(trove.router, prefix="/api/v1", tags=["trove"])  # Trove trading (Nigerian/US stocks)
app.include_router(akshare.router, prefix="/api/v1", tags=["akshare"])  # AKShare Chinese stocks
app.include_router(akshare_settings.router, tags=["akshare-settings"])  # AKShare settings


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