import { useEffect, useRef, useCallback } from 'react';

interface UseWebSocketOptions {
  /** WebSocket 连接地址 */
  url: string;
  /** 收到消息时的回调 */
  onMessage?: (data: unknown) => void;
  /** 连接建立时的回调 */
  onOpen?: () => void;
  /** 连接关闭时的回调 */
  onClose?: () => void;
  /** 发生错误时的回调 */
  onError?: (error: Event) => void;
  /** 是否自动连接，默认 true */
  autoConnect?: boolean;
}

/**
 * WebSocket Hook
 * 封装 WebSocket 连接的生命周期管理
 */
export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  autoConnect = true,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected:', url);
      onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage?.(data);
      } catch {
        onMessage?.(event.data);
      }
    };

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected');
      onClose?.();
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      onError?.(error);
    };
  }, [url, onMessage, onOpen, onClose, onError]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return { connect, disconnect, send };
}
