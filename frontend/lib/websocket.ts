/**
 * WebSocket Client for Jasper Trades
 * Provides real-time connections to backend WebSocket streams
 * 
 * Endpoints:
 * - ws://localhost:8000/ws/prices - Real-time price updates
 * - ws://localhost:8000/ws/signals - Trading signals
 * - ws://localhost:8000/ws/trades - Trade executions
 * - ws://localhost:8000/ws/portfolio - Portfolio updates
 * - ws://localhost:8000/ws/risk - Risk metrics
 */

export type WebSocketRoom = 'prices' | 'signals' | 'trades' | 'portfolio' | 'risk';

export type WebSocketMessage = {
  type: string;
  data: any;
  timestamp?: string;
};

export type WebSocketHandler = (message: WebSocketMessage) => void;

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// Simple logger (replaces structlog for browser)
const logger = {
  info: (msg: string, ...args: any[]) => console.log(`[INFO] ${msg}`, ...args),
  warn: (msg: string, ...args: any[]) => console.warn(`[WARN] ${msg}`, ...args),
  error: (msg: string, ...args: any[]) => console.error(`[ERROR] ${msg}`, ...args),
};

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private handlers: Map<WebSocketRoom, Set<WebSocketHandler>> = new Map();
  private shouldReconnect = true;

  constructor(baseUrl?: string) {
    const apiProtocol = baseUrl?.startsWith('https') ? 'wss' : 'ws';
    const apiHost = baseUrl?.replace(/^https?:\/\//, '') || 'localhost:8000';
    this.url = `${apiProtocol}://${apiHost}`;
  }

  /**
   * Connect to a specific WebSocket room
   */
  connect(room: WebSocketRoom, handler: WebSocketHandler): void {
    if (!this.handlers.has(room)) {
      this.handlers.set(room, new Set());
    }
    this.handlers.get(room)!.add(handler);

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.shouldReconnect = true;
      this.initializeConnection(room);
    }
  }

  /**
   * Disconnect from a specific room
   */
  disconnect(room: WebSocketRoom, handler?: WebSocketHandler): void {
    if (handler && this.handlers.has(room)) {
      this.handlers.get(room)!.delete(handler);
    }

    if (!this.handlers.get(room)?.size) {
      this.handlers.delete(room);
    }

    if (this.handlers.size === 0) {
      this.shouldReconnect = false;
      this.ws?.close();
    }
  }

  /**
   * Subscribe to symbols in a room (for prices)
   */
  subscribe(room: WebSocketRoom, symbols: string[]): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols,
      }));
    }
  }

  /**
   * Get current connection status
   */
  getStatus(): ConnectionStatus {
    return this.status;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.status === 'connected';
  }

  /**
   * Disconnect all and stop reconnecting
   */
  destroy(): void {
    this.shouldReconnect = false;
    this.handlers.clear();
    this.ws?.close();
    this.ws = null;
  }

  private initializeConnection(room: WebSocketRoom): void {
    if (this.ws) {
      this.ws.close();
    }

    this.status = 'connecting';
    const wsUrl = `${this.url}/ws/${room}`;
    
    logger.info(`[WebSocket] Connecting to ${wsUrl}...`);
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      logger.info(`[WebSocket] Connected to ${room}`);
      this.status = 'connected';
      this.reconnectAttempts = 0;
    };

    this.ws.onclose = () => {
      logger.info(`[WebSocket] Disconnected from ${room}`);
      this.status = 'disconnected';

      if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        logger.info(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})...`);
        setTimeout(() => this.initializeConnection(room), delay);
      }
    };

    this.ws.onerror = (error) => {
      logger.warn(`[WebSocket] Connection error for ${room}`, error);
      this.status = 'error';
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(room, message);
      } catch (e) {
        logger.warn(`[WebSocket] Failed to parse message:`, e);
      }
    };
  }

  private handleMessage(room: WebSocketRoom, message: WebSocketMessage): void {
    const handlers = this.handlers.get(room);
    if (!handlers) return;

    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (e) {
        console.error(`[WebSocket] Handler error in ${room}:`, e);
      }
    });
  }
}

// Singleton instance
export const websocketClient = new WebSocketClient();

// Helper functions for usePriceStream hook
export function getWebSocketStatus(): ConnectionStatus {
  return websocketClient.getStatus();
}

export function isWebSocketConnected(): boolean {
  return websocketClient.isConnected();
}