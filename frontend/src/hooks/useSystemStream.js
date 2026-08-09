/**
 * hooks/useSystemStream.js
 *
 * Subscribes to the WebSocket at /ws and maintains the latest state
 * for four system event types:
 *   graph.updated   — Knowledge Graph node/edge counts after a build
 *   tpke.evolved    — TPKE window results (created/strengthened/decayed/pruned)
 *   models.retrained— Agent metrics after retraining
 *   store.appended  — CumulativeStore append (period, rows, cumulative_total)
 *
 * Each event carries a `received_at` ISO timestamp set on arrival.
 * Reconnects with exponential backoff (1s → 2s → 4s … cap 30s).
 * On reconnect, fetches /api/v1/cycle/status to resync cumulative_total.
 */

import { useEffect, useRef, useCallback, useReducer } from 'react'

const BASE_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const WS_URL = BASE_API_URL.replace(/^http/, 'ws') + '/ws'

const initialState = {
  connected: false,
  graph:   null,   // graph.updated payload + received_at
  tpke:    null,   // tpke.evolved payload + received_at
  models:  null,   // models.retrained payload + received_at
  store:   null,   // store.appended payload + received_at
}

function reducer(state, action) {
  const ts = new Date().toISOString()
  switch (action.type) {
    case 'CONNECTED':    return { ...state, connected: true }
    case 'DISCONNECTED': return { ...state, connected: false }
    case 'graph.updated':    return { ...state, graph:  { ...action.payload, received_at: ts } }
    case 'tpke.evolved':     return { ...state, tpke:   { ...action.payload, received_at: ts } }
    case 'models.retrained': return { ...state, models: { ...action.payload, received_at: ts } }
    case 'store.appended':   return { ...state, store:  { ...action.payload, received_at: ts } }
    case 'RESYNC':
      return {
        ...state,
        store: action.cycleStatus
          ? {
              period:           action.cycleStatus.last_period ?? state.store?.period,
              cumulative_total: action.cycleStatus.cumulative_rows ?? state.store?.cumulative_total,
              rows:             state.store?.rows ?? 0,
              received_at:      ts,
            }
          : state.store,
      }
    default: return state
  }
}

export function useSystemStream() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef        = useRef(null)
  const backoffRef   = useRef(1000)
  const timerRef     = useRef(null)
  const destroyedRef = useRef(false)

  const resync = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_API_URL}/api/v1/cycle/status`)
      if (!res.ok) return
      const data = await res.json()
      dispatch({ type: 'RESYNC', cycleStatus: data })
    } catch (_) {}
  }, [])

  const connect = useCallback(() => {
    if (destroyedRef.current) return
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      backoffRef.current = 1000
      dispatch({ type: 'CONNECTED' })
      resync()
    }

    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }
      const SYSTEM_TYPES = ['graph.updated', 'tpke.evolved', 'models.retrained', 'store.appended']
      if (SYSTEM_TYPES.includes(msg.type)) {
        dispatch({ type: msg.type, payload: msg })
      }
    }

    ws.onerror = () => {}

    ws.onclose = () => {
      dispatch({ type: 'DISCONNECTED' })
      if (destroyedRef.current) return
      timerRef.current = setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 2, 30_000)
        connect()
      }, backoffRef.current)
    }
  }, [resync])

  useEffect(() => {
    destroyedRef.current = false
    connect()
    return () => {
      destroyedRef.current = true
      clearTimeout(timerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  return {
    connected: state.connected,
    graph:     state.graph,
    tpke:      state.tpke,
    models:    state.models,
    store:     state.store,
  }
}
