---
name: websocket-heartbeat-production-fix
description: Fix WebSocket disconnect loops by implementing ping/pong heartbeat mechanism for production deployments
source: auto-skill
extracted_at: '2026-06-09T19:55:00.000Z'
---

# WebSocket Heartbeat for Production Stability

## Problem

WebSocket connections drop after 15-30 seconds of idle time due to:
- Firewall/proxy timeouts on idle connections
- Browser closing "dead" connections
- No traffic to keep connection alive

**Symptoms:**
```
[INFO] [WebSocket] Connected to prices
[INFO] [WebSocket] Disconnected from prices
[INFO] [WebSocket] Reconnecting in 1000ms (attempt 1)...
[INFO] [WebSocket] Connected to prices
[INFO] [WebSocket] Disconnected from prices
```

## Solution: Ping/Pong Heartbeat

Backend sends `PING` every 25 seconds → Client auto-responds with `PONG` → Connection stays alive.

## Implementation

### 1. Backend (`backend/app/api/websocket/streams.py`)

```python
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
                await manager.send_personal(websocket, {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                })
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
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=heartbeat_interval * 2
                )
                
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
```

**Key points:**
- `heartbeat_interval = 25` seconds (less than typical 30-60s firewall timeout)
- `asyncio.wait_for()` with 2x interval timeout prevents blocking forever
- Heartbeat task runs concurrently with message handling
- Task is cancelled on disconnect to prevent resource leaks

### 2. Frontend (`frontend/lib/websocket.ts`)

```typescript
private handleMessage(room: WebSocketRoom, message: WebSocketMessage): void {
  const handlers = this.handlers.get(room);
  if (!handlers) return;

  // Auto-respond to ping with pong to keep connection alive
  if (message.type === 'ping') {
    this.sendPong(room);
  }

  handlers.forEach(handler => {
    try {
      handler(message);
    } catch (e) {
      console.error(`[WebSocket] Handler error in ${room}:`, e);
    }
  });
}

/**
 * Send pong response to keep connection alive
 */
private sendPong(room: WebSocketRoom): void {
  if (this.ws && this.ws.readyState === WebSocket.OPEN) {
    this.ws.send(JSON.stringify({
      type: 'pong',
      timestamp: new Date().toISOString(),
      room,
    }));
  }
}
```

**Key points:**
- Silent auto-response (no console spam)
- Only sends if connection is open
- Includes timestamp for debugging

### 3. Production Environment Variables

**Backend (`backend/.env.render`):**
```env
CORS_ORIGINS="http://localhost:3000,https://jasper-trades.vercel.app"
NEXT_PUBLIC_WS_URL="wss://jasper-trades.onrender.com"
NEXT_PUBLIC_API_URL="https://jasper-trades.onrender.com"
```

**Frontend (Vercel Environment Variables):**
```env
NEXT_PUBLIC_API_URL=https://jasper-trades.onrender.com
NEXT_PUBLIC_WS_URL=wss://jasper-trades.onrender.com
```

**Critical:** Use `wss://` (secure WebSocket) for production, not `ws://`

### 4. Build Configuration

**`frontend/next.config.ts`:**
```typescript
const nextConfig: NextConfig = {
  // ... other config
  env: {
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || '',
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
  },
};
```

**`render-build.sh`:**
```bash
echo "🏗️  Building Next.js frontend..."
echo "   API URL: ${NEXT_PUBLIC_API_URL:-'not set'}"
echo "   WS URL:  ${NEXT_PUBLIC_WS_URL:-'not set'}"
NEXT_TELEMETRY_DISABLED=1 npm run build
```

## Testing

**Local testing:**
```bash
# Backend runs on port 8000
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend runs on port 3000
cd frontend && npm run dev
```

**Expected console output:**
```
[INFO] [WebSocket] Connecting to ws://localhost:8000/ws/prices...
[INFO] [WebSocket] Connected to prices
# Every 25 seconds:
[INFO] Received PING from server [2026-06-09T18:50:48.099828]
[INFO] Sent PONG response
```

**Production testing:**
1. Open browser console on `https://your-app.vercel.app`
2. Verify single "Connected" message (no reconnect loops)
3. Check Network tab → WebSocket shows continuous connection
4. Backend logs show `Heartbeat ping #X sent` every 25s

## Deployment Checklist

- [ ] Backend heartbeat code deployed to Render
- [ ] Frontend auto-pong code deployed to Vercel
- [ ] `NEXT_PUBLIC_WS_URL` set in Vercel (wss://)
- [ ] `CORS_ORIGINS` includes Vercel domain in Render
- [ ] Test: WebSocket stays connected > 60 seconds
- [ ] Test: No repeated disconnect/reconnect cycles

## Troubleshooting

### Still seeing disconnects

**Check:**
1. Backend logs for `Heartbeat ping #X sent` messages
2. Browser console for ping/pong messages
3. Network tab → WebSocket frame timing

**Fix:**
- Reduce `heartbeat_interval` to 15 seconds
- Check firewall/proxy configuration
- Verify `wss://` protocol in production

### PING sent but no PONG received

**Check:**
1. Frontend `handleMessage()` is called
2. `message.type === 'ping'` condition matches
3. WebSocket readyState is OPEN

**Fix:**
- Add logging in `sendPong()` to verify it's called
- Check if frontend build included env vars

### CORS errors after adding heartbeat

**Fix:**
```env
# In Render dashboard
CORS_ORIGINS="http://localhost:3000,https://jasper-trades.vercel.app"
```

## Why 25 Seconds?

| Timeout Source | Typical Value | Safety Margin |
|----------------|---------------|---------------|
| Browser idle timeout | 30-60s | ✓ |
| Nginx proxy_read_timeout | 60s | ✓ |
| AWS ALB idle timeout | 60s | ✓ |
| Cloudflare WebSocket timeout | 100s | ✓ |
| Render proxy timeout | 30-60s | ✓ |

**25 seconds** provides buffer below all common timeouts while minimizing network chatter.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Vercel Frontend                                            │
│  https://jasper-trades.vercel.app                           │
│                                                              │
│  WebSocket client:                                          │
│  - Connects to wss://backend.onrender.com/ws/prices         │
│  - Auto-responds PONG to PING (every 25s)                   │
│  - Updates UI with price data                               │
└─────────────────────────────────────────────────────────────┘
                          ↕ wss:// (secure WebSocket)
┌─────────────────────────────────────────────────────────────┐
│  Render Backend                                             │
│  https://jasper-trades.onrender.com                         │
│                                                              │
│  FastAPI WebSocket endpoint /ws/prices:                     │
│  - Sends PING every 25 seconds                              │
│  - Logs ping count for debugging                            │
│  - Broadcasts price updates to subscribers                  │
│  - Cleans up disconnected clients                           │
└─────────────────────────────────────────────────────────────┘
```

## Cost Impact

**Zero additional cost:**
- Heartbeat messages are tiny (<100 bytes)
- 2 messages per 25s = ~7KB/hour
- Well within free tier limits (Render: 500 hours/month, Vercel: 100GB bandwidth)