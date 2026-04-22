/**
 * WebSocket composable — connects to the backend WS endpoint and dispatches
 * events to Pinia stores for real-time updates.
 *
 * Features:
 * - Auto-connect on mount, auto-disconnect on unmount
 * - Exponential backoff reconnection (1s → 2s → 4s → … → 30s)
 * - Ping/pong keep-alive every 30s
 * - Pauses when tab is hidden, resumes on visibility
 * - Typed event listeners
 */

import { ref, onMounted, onUnmounted, getCurrentInstance } from 'vue'

export interface WsEvent {
  type: string
  data: Record<string, unknown>
}

type EventHandler = (data: Record<string, unknown>) => void

const INITIAL_RETRY_MS = 1_000
const MAX_RETRY_MS = 30_000
const PING_INTERVAL_MS = 30_000

// Shared state (singleton across all component instances)
let ws: WebSocket | null = null
let retryTimeout: ReturnType<typeof setTimeout> | null = null
let pingInterval: ReturnType<typeof setInterval> | null = null
let retryMs = INITIAL_RETRY_MS
const listeners = new Map<string, Set<EventHandler>>()

export const wsConnected = ref(false)

function getWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/v1/ws`
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  try {
    ws = new WebSocket(getWsUrl())
  } catch {
    scheduleRetry()
    return
  }

  ws.onopen = () => {
    wsConnected.value = true
    retryMs = INITIAL_RETRY_MS
    startPing()
  }

  ws.onmessage = (event) => {
    try {
      const msg: WsEvent = JSON.parse(event.data)
      if (msg.type === 'pong') return
      dispatch(msg.type, msg.data)
    } catch {
      // Ignore malformed messages
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    stopPing()
    if (!document.hidden) {
      scheduleRetry()
    }
  }

  ws.onerror = () => {
    // onclose will fire after onerror
  }
}

function disconnect() {
  if (retryTimeout) {
    clearTimeout(retryTimeout)
    retryTimeout = null
  }
  stopPing()
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
  wsConnected.value = false
}

function scheduleRetry() {
  if (retryTimeout) return
  retryTimeout = setTimeout(() => {
    retryTimeout = null
    retryMs = Math.min(retryMs * 2, MAX_RETRY_MS)
    connect()
  }, retryMs)
}

function startPing() {
  stopPing()
  pingInterval = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }, PING_INTERVAL_MS)
}

function stopPing() {
  if (pingInterval) {
    clearInterval(pingInterval)
    pingInterval = null
  }
}

function dispatch(type: string, data: Record<string, unknown>) {
  const handlers = listeners.get(type)
  if (handlers) {
    for (const handler of handlers) {
      try {
        handler(data)
      } catch (e) {
        console.error(`[WS] Error in handler for "${type}":`, e)
      }
    }
  }
}

/**
 * Register a listener for a specific event type. Returns an unsubscribe function.
 * If called inside a Vue setup context, automatically cleans up on unmount.
 */
export function onWsEvent(type: string, handler: EventHandler): () => void {
  if (!listeners.has(type)) {
    listeners.set(type, new Set())
  }
  listeners.get(type)!.add(handler)

  const unsub = () => {
    listeners.get(type)?.delete(handler)
  }

  // Auto-cleanup when the component unmounts
  if (getCurrentInstance()) {
    onUnmounted(unsub)
  }

  return unsub
}

/** Remove all listeners for a specific event type. */
export function offWsEvent(type: string) {
  listeners.delete(type)
}

// Visibility handling — reconnect when tab becomes visible
function onVisibilityChange() {
  if (document.hidden) {
    // Don't disconnect, just stop retrying
    if (retryTimeout) {
      clearTimeout(retryTimeout)
      retryTimeout = null
    }
  } else {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      retryMs = INITIAL_RETRY_MS
      connect()
    }
  }
}

/**
 * Call this composable once in App.vue or a root layout component.
 * It manages the singleton WebSocket connection lifecycle.
 */
export function useWebSocket() {
  onMounted(() => {
    connect()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    disconnect()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return { connected: wsConnected }
}
