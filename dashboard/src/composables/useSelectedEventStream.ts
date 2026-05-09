import { ref } from 'vue';
import { EventSourcePolyfill } from 'event-source-polyfill';

type StreamEventHandler = (eventName: string, payload: any, raw: MessageEvent) => void;

type StreamOptions = {
  eventNames: string[];
  streamUrl: (id: string, afterSeq: number) => string;
  getAfterSeq: () => number;
  onEvent: StreamEventHandler;
  onFallback?: (id: string) => Promise<void> | void;
  shouldReconnect?: (id: string) => boolean;
  reconnectDelay?: number;
  fallbackInterval?: number;
};

export function useSelectedEventStream(options: StreamOptions) {
  const activeId = ref('');
  const connected = ref(false);
  let eventSource: any = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let fallbackTimer: ReturnType<typeof setInterval> | null = null;

  function open(id: string) {
    close();
    activeId.value = id;
    if (!id) return;

    const token = localStorage.getItem('token') || '';
    eventSource = new EventSourcePolyfill(options.streamUrl(id, options.getAfterSeq()), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      heartbeatTimeout: 60000,
    });

    for (const name of options.eventNames) {
      eventSource.addEventListener(name, (event: MessageEvent) => {
        if (activeId.value !== id) return;
        try {
          const payload = event.data ? JSON.parse(event.data) : {};
          options.onEvent(name, payload, event);
        } catch {
          options.onEvent(name, {}, event);
        }
      });
    }

    eventSource.onopen = () => {
      if (activeId.value !== id) return;
      connected.value = true;
      stopFallback();
    };
    eventSource.onerror = () => {
      if (activeId.value !== id) return;
      connected.value = false;
      startFallback(id);
      scheduleReconnect(id);
    };
  }

  function close() {
    activeId.value = '';
    connected.value = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    stopFallback();
  }

  function scheduleReconnect(id: string) {
    if (reconnectTimer) return;
    if (options.shouldReconnect && !options.shouldReconnect(id)) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (activeId.value === id && (!options.shouldReconnect || options.shouldReconnect(id))) {
        open(id);
      }
    }, options.reconnectDelay || 1500);
  }

  function startFallback(id: string) {
    if (!options.onFallback || fallbackTimer) return;
    options.onFallback(id);
    fallbackTimer = setInterval(() => {
      if (activeId.value !== id) return;
      if (options.shouldReconnect && !options.shouldReconnect(id)) {
        stopFallback();
        return;
      }
      options.onFallback?.(id);
    }, options.fallbackInterval || 3000);
  }

  function stopFallback() {
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }
  }

  return {
    activeId,
    connected,
    open,
    close,
  };
}
