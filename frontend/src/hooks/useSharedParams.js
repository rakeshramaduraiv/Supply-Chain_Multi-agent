import { useSearchParams, useNavigate } from 'react-router-dom'
import { useCallback } from 'react'

export function useSharedParams() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const entityId    = searchParams.get('entityId') || ''
  const period      = searchParams.get('period') || '2024-01'
  const region      = searchParams.get('region') || ''
  const issueId     = searchParams.get('issueId') || ''
  const supplierId  = searchParams.get('supplierId') || ''
  const warehouseId = searchParams.get('warehouseId') || ''
  const productId   = searchParams.get('productId') || ''
  const type        = searchParams.get('type') || ''

  const setParam = useCallback((key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (value) {
        next.set(key, value)
      } else {
        next.delete(key)
      }
      return next
    })
  }, [setSearchParams])

  const setParams = useCallback((overrides) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      Object.entries(overrides).forEach(([key, val]) => {
        if (val) {
          next.set(key, val)
        } else {
          next.delete(key)
        }
      })
      return next
    })
  }, [setSearchParams])

  const navigateToPage = useCallback((path, overrides = {}) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(overrides).forEach(([key, val]) => {
      if (val) {
        next.set(key, val)
      } else {
        next.delete(key)
      }
    })
    navigate({
      pathname: path,
      search: next.toString(),
    })
  }, [navigate, searchParams])

  return {
    entityId,
    period,
    region,
    issueId,
    supplierId,
    warehouseId,
    productId,
    type,
    setParam,
    setParams,
    navigateToPage,
  }
}
