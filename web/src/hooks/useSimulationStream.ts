import { useState, useEffect, useRef, useCallback } from 'react';

export interface SimulationEvent {
  type: string;
  topic: string;
  data: any;
  ts: string;
}

export interface SimulationSnapshot {
  status: 'idle' | 'running' | 'stopped';
  tick: number;
  kpis: {
    revenue: number;
    profit: number;
    units_sold: number;
  };
  agents: Array<{
    slug: string;
    display_name: string;
    state: string;
  }>;
  timestamp: string;
}

interface UseSimulationStreamOptions {
  url?: string;
  topics?: string[];
  token?: string | null;
  onEvent?: (event: SimulationEvent) => void;
}

export function useSimulationStream({
  url = 'ws://localhost:8000/ws/realtime',
  topics = ['simulation.events', 'simulation.metrics'],
  token,
  onEvent,
}: UseSimulationStreamOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SimulationEvent | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | undefined>(undefined);
  const mountedRef = useRef(true);

  // Keep latest onEvent callback without triggering re-effects
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Construct URL with token if present
    const wsUrl = new URL(url);
    if (token) {
      wsUrl.searchParams.set('token', token);
    }

    const ws = new WebSocket(wsUrl.toString());
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      console.log('WebSocket connected');
      setIsConnected(true);
      
      // Subscribe to topics
      topics.forEach(topic => {
        ws.send(JSON.stringify({ type: 'subscribe', topic }));
      });
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'event') {
          const simEvent: SimulationEvent = {
            type: data.type,
            topic: data.topic,
            data: data.data,
            ts: data.ts
          };
          setLastEvent(simEvent);
          onEventRef.current?.(simEvent);

          // Update snapshot if event contains snapshot data
          if (data.topic === 'simulation.snapshot') {
            setSnapshot(data.data);
          }
        } else if (data.type === 'pong') {
          // Handle pong if needed
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      console.log('WebSocket disconnected');
      setIsConnected(false);
      wsRef.current = null;
      
      // Attempt reconnect after delay
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (mountedRef.current) connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      ws.close();
    };
  }, [url, topics, token]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  // Heartbeat to keep connection alive
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return {
    isConnected,
    lastEvent,
    snapshot,
  };
}