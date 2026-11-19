/**
 * useEnterpriseStore — Centralized Application State
 *
 * Mounts ONCE in AppShell. Every page subscribes via context.
 * Responsibilities:
 *   1. Single upload handler — one function, all pages invalidated
 *   2. WebSocket-driven invalidation scoped to supply chain keys only
 *   3. Last upload timestamp broadcast to all pages
 *   4. Global loading / error state for the upload pipeline
 *
 * Usage in any page:
 *   const { uploadActual, lastUpload, isUploading } = useEnterpriseStore()
 */

import { createContext, useContext, useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { SUPPLY_CHAIN_QUERY_KEYS } from './useSupplyChainData'

const EnterpriseStoreContext = createContext(null)

export function EnterpriseStoreProvider({ children }) {
  const qc = useQueryClient()
  const [isUploading, setIsUploading] = useState(false)
  const [lastUpload, setLastUpload] = useState(null)   // { period, rows, accuracy, timestamp }
  const [uploadError, setUploadError] = useState(null)
  const abortRef = useRef(null)

  /**
   * invalidateAll — invalidates every supply chain query.
   * Called after upload, after WS event, or manually.
   */
  const invalidateAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.all })
  }, [qc])

  /**
   * uploadActual — single upload handler for the entire platform.
   * Any page can call this. All pages refresh automatically on success.
   *
   * @param {File}   file
   * @param {string} period  e.g. '2019-01'
   * @returns {Promise<object>} upload result
   */
  const uploadActual = useCallback(async (file, period) => {
    setIsUploading(true)
    setUploadError(null)
    try {
      const result = await api.uploadActual(file, `Actual upload for ${period}`).then(r => r.data)
      setLastUpload({
        period,
        rows: result.row_count ?? result.records_loaded ?? 0,
        accuracy: result.mape_val != null ? (100 - result.mape_val).toFixed(1) : null,
        timestamp: new Date().toISOString(),
        result,
      })
      // Invalidate every supply chain query — all pages refresh
      invalidateAll()
      return result
    } catch (err) {
      setUploadError(err.message || 'Upload failed')
      throw err
    } finally {
      setIsUploading(false)
    }
  }, [invalidateAll])

  const value = {
    isUploading,
    lastUpload,
    uploadError,
    uploadActual,
    invalidateAll,
  }

  return (
    <EnterpriseStoreContext.Provider value={value}>
      {children}
    </EnterpriseStoreContext.Provider>
  )
}

export function useEnterpriseStore() {
  const ctx = useContext(EnterpriseStoreContext)
  if (!ctx) throw new Error('useEnterpriseStore must be used inside EnterpriseStoreProvider')
  return ctx
}
