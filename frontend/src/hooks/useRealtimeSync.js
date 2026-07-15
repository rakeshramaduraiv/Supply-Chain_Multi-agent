import { useEffect, useState, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useToast } from '../components/ui/Toast'
import { SUPPLY_CHAIN_QUERY_KEYS } from './useSupplyChainData'

const BASE_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function useRealtimeSync() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    // Convert HTTP base to WebSocket base
    const wsBase = BASE_API_URL.replace(/^http/, 'ws')
    const wsUrl = `${wsBase}/api/v1/ws`

    let reconnectTimeout = null

    function connect() {
      console.log(`[RealtimeSync] Connecting to ${wsUrl}...`)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[RealtimeSync] Connected successfully.')
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.event) {
            console.log(`[RealtimeSync] Received event: ${payload.event}`, payload.data)
            
            // Invalidate all queries to trigger refetching
            queryClient.invalidateQueries()
            
            // Trigger UI notification toast to indicate sync action
            if (toast) {
              toast.info(`Database Sync: ${payload.event}. Refreshing views...`)
            }
          }
        } catch (e) {
          console.error('[RealtimeSync] Error parsing message:', e)
        }
      }

      ws.onclose = () => {
        console.warn('[RealtimeSync] Socket closed. Retrying in 5 seconds...')
        setIsConnected(false)
        reconnectTimeout = setTimeout(connect, 5000)
      }

      ws.onerror = (err) => {
        console.error('[RealtimeSync] Socket error:', err)
        ws.close()
      }
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
      }
    }
  }, [queryClient, toast])

  return { isConnected }
}
