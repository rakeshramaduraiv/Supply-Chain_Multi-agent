/**
 * hooks/useCycleStream.js
 *
 * Connects to /ws, filters type="cycle.stage" and "cycle.complete" events,
 * and maintains a stages map keyed by stage number for the active cycle.
 *
 * Reconnects with exponential backoff (1s → 2s → 4s … cap 30s).
 * On reconnect, if a cycleId is active, calls GET /api/v1/cycle/{id}/stages
 * to resync any events missed during the disconnect.
 */

import { useEffect, useRef, useCallback, useReducer } from 'react'

const BASE_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const WS_URL = BASE_API_URL.replace(/^http/, 'ws') + '/api/v1/ws'

// stages: { [stageNum]: eventObject }
// complete: cycle.complete payload or null
// connected: bool
const initialState = {
  cycleId: null,
  stages: {},
  complete: null,
  connected: false,
}

function reducer(state, action) {
  switch (action.type) {
    case 'CONNECTED':
      return { ...state, connected: true }
    case 'DISCONNECTED':
      return { ...state, connected: false }
    case 'SET_CYCLE':
      // New cycle — reset stages and complete
      if (action.cycleId !== state.cycleId) {
        return { ...state, cycleId: action.cycleId, stages: {}, complete: null }
      }
      return state
    case 'STAGE_EVENT': {
      const ev = action.event
      // Only accept events for the active cycleId (or if no cycleId set yet)
      if (state.cycleId && ev.cycle_id !== state.cycleId) return state
      return {
        ...state,
        cycleId: ev.cycle_id,
        stages: { ...state.stages, [ev.stage]: ev },
      }
    }
    case 'COMPLETE_EVENT':
      if (state.cycleId && action.event.cycle_id !== state.cycleId) return state
      return { ...state, complete: action.event }
    case 'RESYNC': {
      // Replay a list of events from the REST resync endpoint
      const newStages = { ...state.stages }
      let newComplete = state.complete
      for (const ev of action.events) {
        if (ev.type === 'cycle.stage') newStages[ev.stage] = ev
        else if (ev.type === 'cycle.complete') newComplete = ev
      }
      return { ...state, stages: newStages, complete: newComplete }
    }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

export function useCycleStream(cycleId = null) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef        = useRef(null)
  const backoffRef   = useRef(1000)
  const timerRef     = useRef(null)
  const destroyedRef = useRef(false)
  const cycleIdRef   = useRef(cycleId)

  // Keep ref in sync so the WS handler always sees the latest cycleId
  useEffect(() => {
    cycleIdRef.current = cycleId
    if (cycleId) dispatch({ type: 'SET_CYCLE', cycleId })
  }, [cycleId])

  const resync = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await fetch(`${BASE_API_URL}/api/v1/cycle/${id}/stages`)
      if (!res.ok) return
      const events = await res.json()
      dispatch({ type: 'RESYNC', events })
    } catch (_) {
      // resync is best-effort
    }
  }, [])

  const connect = useCallback(() => {
    if (destroyedRef.current) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      backoffRef.current = 1000          // reset backoff on successful connect
      dispatch({ type: 'CONNECTED' })
      // Resync any missed events for the active cycle
      if (cycleIdRef.current) resync(cycleIdRef.current)
    }

    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }

      if (msg.type === 'cycle.stage') {
        dispatch({ type: 'STAGE_EVENT', event: msg })
      } else if (msg.type === 'cycle.complete') {
        dispatch({ type: 'COMPLETE_EVENT', event: msg })
      }
      // Other event types (heartbeat, generic broadcast) are ignored here
    }

    ws.onerror = () => {}

    ws.onclose = () => {
      dispatch({ type: 'DISCONNECTED' })
      if (destroyedRef.current) return
      // Exponential backoff: 1s → 2s → 4s … capped at 30s
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

  const reset = useCallback(() => dispatch({ type: 'RESET' }), [])

  return {
    connected:  state.connected,
    cycleId:    state.cycleId,
    stages:     state.stages,      // { [stageNum]: event }
    complete:   state.complete,    // cycle.complete event or null
    reset,
    resync,
  }
}
