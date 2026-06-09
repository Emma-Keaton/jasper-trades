/**
 * React Hook for Real-Time Price Updates
 * Connects to WebSocket price stream and updates holdings prices
 */

import { useEffect, useRef, useCallback } from 'react';
import { websocketClient, WebSocketMessage, ConnectionStatus } from '../lib/websocket';

interface PriceUpdate {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
}

interface UsePriceStreamOptions {
  onPriceUpdate?: (update: PriceUpdate) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  symbols?: string[];
}

export function usePriceStream(options: UsePriceStreamOptions = {}) {
  const { onPriceUpdate, onStatusChange, symbols = [] } = options;
  const statusRef = useRef<ConnectionStatus>('disconnected');
  const connectedRef = useRef(false);
  const attemptedRef = useRef(false);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'price_update' && message.data) {
      const priceUpdate: PriceUpdate = {
        symbol: message.data.symbol,
        price: message.data.price,
        change: message.data.change || 0,
        changePercent: message.data.change_percent || 0,
        volume: message.data.volume || 0,
        timestamp: message.data.timestamp || new Date().toISOString(),
      };

      onPriceUpdate?.(priceUpdate);
    }
  }, [onPriceUpdate]);

  useEffect(() => {
    // Only attempt connection once
    if (attemptedRef.current) return;
    attemptedRef.current = true;
    
    // Connect to price stream
    websocketClient.connect('prices', handleMessage);

    // Subscribe to specific symbols if provided
    if (symbols.length > 0) {
      setTimeout(() => {
        websocketClient.subscribe('prices', symbols);
      }, 500); // Wait for connection to establish
    }

    // Poll status for UI updates
    const statusInterval = setInterval(() => {
      const status = websocketClient.getStatus();
      if (status !== statusRef.current) {
        statusRef.current = status;
        onStatusChange?.(status);
      }
    }, 1000);

    return () => {
      clearInterval(statusInterval);
    };
  }, []);

  return {
    isConnected: websocketClient.isConnected(),
    status: websocketClient.getStatus(),
    subscribe: (newSymbols: string[]) => websocketClient.subscribe('prices', newSymbols),
  };
}