import { useEffect, useState, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const BASE_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function useRealtimeSync() {
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    const wsBase = BASE_API_URL.replace(/^http/, 'ws')
    const wsUrl = `${wsBase}/api/v1/ws`
    let reconnectTimeout = null
    let destroyed = false

    let attempts = 0
    function connect() {
      if (destroyed || attempts >= 2) return
      attempts++
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onopen = () => { attempts = 0; setIsConnected(true) }
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.event) queryClient.invalidateQueries({ queryKey: ['supplyChain'] })
        } catch (_) {}
      }
      ws.onerror = () => {}
      ws.onclose = () => {
        setIsConnected(false)
        if (!destroyed && attempts < 2) reconnectTimeout = setTimeout(connect, 5000)
      }
    }

    connect()
    return () => {
      destroyed = true
      clearTimeout(reconnectTimeout)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [queryClient])

  return { isConnected }
}
