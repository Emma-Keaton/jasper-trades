"""
WebSocket Streams for Real-Time Market Data
Replaces polling with push-based updates for prices, trades, and signals
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import asyncio
import json
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = set()
        self.active_connections[room].add(websocket)
        logger.info(f"WebSocket connected to {room}", total=len(self.active_connections[room]))
    
    def disconnect(self, websocket: WebSocket, room: str):
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]
        logger.info(f"WebSocket disconnected from {room}")
    
    async def broadcast(self, room: str, message: dict):
        """Send message to all connections in a room"""
        if room not in self.active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections[room]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections[room].discard(conn)
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to specific connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")


manager = ConnectionManager()


# Price update queue
price_queue = asyncio.Queue()


async def price_publisher():
    """Background task that publishes price updates to WebSocket subscribers"""
    while True:
        try:
            # Get price update from queue
            price_data = await price_queue.get()
            
            # Broadcast to all subscribers
            await manager.broadcast("prices", {
                "type": "price_update",
                "data": price_data
            })
            
            price_queue.task_done()
        except Exception as e:
            logger.error(f"Price publisher error: {e}")
            await asyncio.sleep(1)


# Signal update queue
signal_queue = asyncio.Queue()


async def signal_publisher():
    """Background task that publishes signal updates"""
    while True:
        try:
            signal_data = await signal_queue.get()
            
            # Broadcast to signal subscribers
            await manager.broadcast("signals", {
                "type": "signal_update",
                "data": signal_data
            })
            
            signal_queue.task_done()
        except Exception as e:
            logger.error(f"Signal publisher error: {e}")
            await asyncio.sleep(1)


# Trade execution queue
trade_queue = asyncio.Queue()


async def trade_publisher():
    """Background task that publishes trade execution updates"""
    while True:
        try:
            trade_data = await trade_queue.get()
            
            # Broadcast to trade subscribers
            await manager.broadcast("trades", {
                "type": "trade_update",
                "data": trade_data
            })
            
            trade_queue.task_done()
        except Exception as e:
            logger.error(f"Trade publisher error: {e}")
            await asyncio.sleep(1)


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for real-time price updates"""
    await manager.connect(websocket, "prices")
    
    # Start heartbeat to keep connection alive
    heartbeat_interval = 25  # seconds - must be less than typical firewall timeout (30-60s)
    
    async def send_heartbeat():
        """Send periodic ping to client"""
        ping_count = 0
        while True:
            await asyncio.sleep(heartbeat_interval)
            ping_count += 1
            try:
                await manager.send_personal(websocket, {"type": "ping", "timestamp": datetime.utcnow().isoformat()})
                logger.info(f"Heartbeat ping #{ping_count} sent")
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                break
    
    # Start heartbeat task
    heartbeat_task = asyncio.create_task(send_heartbeat())
    
    try:
        while True:
            try:
                # Use wait_for to allow heartbeat to continue even if no messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=heartbeat_interval * 2)
                
                # Handle subscription changes
                try:
                    message = json.loads(data)
                    if message.get("action") == "subscribe":
                        symbols = message.get("symbols", [])
                        logger.info(f"Client subscribed to: {symbols}")
                    # Handle pong response
                    elif message.get("type") == "pong":
                        logger.debug("Received pong from client")
                except json.JSONDecodeError:
                    pass
            except asyncio.TimeoutError:
                # No message received, but connection is still alive
                # Heartbeat is still running, just continue waiting
                continue
    except WebSocketDisconnect:
        heartbeat_task.cancel()
        manager.disconnect(websocket, "prices")
        logger.info("Price WebSocket client disconnected")
    except Exception as e:
        heartbeat_task.cancel()
        manager.disconnect(websocket, "prices")
        logger.error(f"Price WebSocket error: {e}")
        raise


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """WebSocket endpoint for real-time signal updates"""
    await manager.connect(websocket, "signals")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "signals")
        logger.info("Signal WebSocket client disconnected")


@router.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    """WebSocket endpoint for real-time trade execution updates"""
    await manager.connect(websocket, "trades")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Trade WS received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "trades")
        logger.info("Trade WebSocket client disconnected")


@router.websocket("/ws/portfolio")
async def websocket_portfolio(websocket: WebSocket):
    """WebSocket endpoint for portfolio updates"""
    await manager.connect(websocket, "portfolio")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "portfolio")


@router.websocket("/ws/forex")
async def websocket_forex(websocket: WebSocket):
    """WebSocket endpoint for forex rate updates.

    Clients connect to this room to receive real-time NGN/USD rate updates.
    Rates are pushed every 60 seconds from the forex polling service.
    """
    await manager.connect(websocket, "forex_rates")
    try:
        while True:
            # Keep connection alive - client just listens for updates
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "forex_rates")


async def start_publisher_tasks():
    """Start background publisher tasks"""
    asyncio.create_task(price_publisher())
    asyncio.create_task(signal_publisher())
    asyncio.create_task(trade_publisher())
    logger.info("WebSocket publisher tasks started")


# Helper functions to publish updates
async def publish_price_update(price_data: dict):
    """Publish price update to WebSocket subscribers.

    Accepts the full payload dict already assembled by callers (symbol, price,
    change, volume, timestamp, source, etc.).
    """
    await price_queue.put(price_data)


async def publish_signal_created(signal_data: dict):
    """Publish new signal to WebSocket subscribers"""
    await signal_queue.put(signal_data)


async def publish_trade_execution(trade_data: dict):
    """Publish trade execution to WebSocket subscribers"""
    await trade_queue.put(trade_data)


async def publish_risk_update(risk_metrics: dict):
    """Publish risk metrics update"""
    await manager.broadcast("risk", {
        "type": "risk_update",
        **risk_metrics,
        "timestamp": datetime.utcnow().isoformat()
    })


async def publish_forex_update(data: dict):
    """
    Publish forex rate update to WebSocket subscribers.

    Args:
        data: Dict with rates, timestamp, and source
        Example: {
            "rates": {"NGN/USD": {"rate": 0.00065, "bid": 0.00064, "ask": 0.00066}},
            "timestamp": "2026-06-11T14:35:00Z",
            "source": "trove"
        }
    """
    await manager.broadcast("forex_rates", {
        "type": "forex_update",
        **data,
    })