"""
Jasper Trades - Superpowered AI Trader
Main FastAPI Application
"""
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import List
import structlog

from app.config import settings
from app.database import get_db, init_db, close_db, async_session
from app.models import Trade, Signal, Portfolio
from app.agents import DirectorAgent, QuantAgent, RiskAgent, ExecutionAgent, agent_registry
from app.nvidia_nim import nvidia_client
from app.brokers import broker_registry, initialize_brokers
from app.services import init_scheduler, get_scheduler
from app.services.market_data_service import market_data_service
from app.services.embedded_openwa import embedded_openwa, get_embedded_openwa

# Kronos integration (optional - 4GB RAM optimized)
try:
    from app.services.kronos import set_memory_limits, configure_torch_cpu
    KRONOS_AVAILABLE = True
except ImportError:
    KRONOS_AVAILABLE = False
    set_memory_limits = lambda **kwargs: None  # type: ignore
    configure_torch_cpu = lambda: None  # type: ignore

# Import API routes
from app.api.v1 import trading, agents, signals, portfolio, health, system, learning, risk, circuit_breaker, chat
from app.api.websocket import streams as websocket_streams
from app.api.v1 import settings as api_settings_router
from app.api.v1 import alpha_factors, backtest, withdrawal
from app.api.v1 import heartbeat, polymarket, debate, ensemble, swarm, quantlib, checkpoint, notify
from app.api.v1 import exness, trading_caps
from app.api.v1 import settings_extensions

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
            await portfolio_service.create_portfolio(
                name="Default",
                initial_cash=100000.0,
                is_paper=True,
                broker="alpaca",
            )
            logger.info("Created default portfolio")

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

    # Start embedded OpenWA (WhatsApp notifications + chat)
    try:
        openwa_started = await embedded_openwa.start()
        if openwa_started:
            logger.info(f"Embedded OpenWA started on port {embedded_openwa.port}")
        else:
            logger.warning("OpenWA not started. To enable WhatsApp: npm install @open-wa/wa-automate")
    except Exception as e:
        logger.warning(f"Embedded OpenWA startup failed: {e}")

    # Start auto-payout scheduler (background task for 50% daily profit payouts)
    try:
        from app.services.payout_scheduler import payout_scheduler
        await payout_scheduler.start()
        logger.info("Auto-payout scheduler started (checks every hour)")
    except Exception as e:
        logger.warning(f"Auto-payout scheduler startup failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Jasper Trades...")

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

    # Stop embedded OpenWA
    try:
        await embedded_openwa.stop()
        logger.info("Embedded OpenWA stopped")
    except Exception as e:
        logger.warning(f"Error stopping OpenWA: {e}")

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

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
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
app.include_router(chat.router, prefix="/api/v1", tags=["whatsapp"])
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
app.include_router(exness.router, prefix="/api/v1", tags=["exness"])
app.include_router(trading_caps.router, prefix="/api/v1", tags=["trading-caps"])
app.include_router(settings_extensions.router, prefix="/api/v1", tags=["settings-extensions"])


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


# For serving frontend in production (optional)
# app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")