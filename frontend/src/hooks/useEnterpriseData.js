/**
 * useEnterpriseData — Single Source of Truth for the entire AMASCI platform.
 *
 * Every page, every chart, every KPI, every metric must derive its values
 * from this hook. No page may compute its own fallback values.
 *
 * Data hierarchy:
 *   DataCo Dataset (180,519 rows) → Backend APIs → This hook → All pages
 *
 * Guarantees:
 *   - The same metric shown on multiple pages is always identical.
 *   - All values are null when backend data is absent (never fabricated).
 *   - Uploading monthly actuals invalidates every query simultaneously.
 */

import { useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useDatasetSummary,
  useDatasetAnalytics,
  useAutoForecast,
  useKpis,
  useGraphStats,
  useTpkeDash,
  useTpkeEdges,
  useRcaStats,
  useRcaDash,
  useRcaHistory,
  useRiskDash,
  useForecastDash,
  useTrends,
  useNetworkPageData,
  SUPPLY_CHAIN_QUERY_KEYS,
} from './useSupplyChainData'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

// ─── Model registry (agent accuracies, feature importances) ─────────────────

function useLatestModels() {
  return useQuery({
    queryKey: ['supplyChain', 'latestModels'],
    queryFn: () => api.getLatestModels().then(r => r.data),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

// ─── Main enterprise hook ────────────────────────────────────────────────────

export function useEnterpriseData() {
  const summaryQ   = useDatasetSummary()
  const analyticsQ = useDatasetAnalytics()
  const forecastQ  = useAutoForecast()
  const kpisQ      = useKpis()
  const graphStatsQ = useGraphStats()
  const tpkeDashQ  = useTpkeDash()
  const tpkeEdgesQ = useTpkeEdges()
  const rcaStatsQ  = useRcaStats()
  const rcaDashQ   = useRcaDash()
  const rcaHistoryQ = useRcaHistory()
  const riskDashQ  = useRiskDash()
  const forecastDashQ = useForecastDash()
  const trendsQ    = useTrends()
  const modelsQ    = useLatestModels()
  const networkData = useNetworkPageData()

  const s  = summaryQ.data   || {}
  const a  = analyticsQ.data || {}
  const f  = forecastQ.data  || {}
  const gs = graphStatsQ.data || {}
  const td = tpkeDashQ.data  || {}
  const models = modelsQ.data || {}

  // ── Dataset ground truth ─────────────────────────────────────────────────
  const totalOrders        = s.total_orders        ?? null
  const lateDeliveryPct    = s.late_delivery_pct   ?? null
  const avgShippingDelay   = s.avg_shipping_delay  ?? null
  const avgSupplierReliability = s.avg_supplier_reliability ?? null
  const dateRangeStart     = s.date_range_start    ?? null
  const dateRangeEnd       = s.date_range_end      ?? null
  const monthlyTrend       = a.monthly_trend       ?? []
  const shippingRisk       = a.shipping_risk       ?? []
  const categoryVolatility = a.category_volatility ?? []
  const riskBreakdown      = a.risk_breakdown      ?? []
  const trainingMetrics    = a.training_metrics    ?? {}

  // ── Knowledge Graph ──────────────────────────────────────────────────────
  const graphVersion   = gs.graph_version   ?? null
  const totalNodes     = networkData.totalNodes || null
  const totalRels      = networkData.totalRels  || null
  const nodeCounts     = networkData.nodeCounts || {}
  const tpkeVersion    = td.version         ?? null
  const tpkeEdgeCount  = td.total_edges     ?? null
  const tpkeAvgConf    = td.avg_confidence  ?? null

  // ── Agent accuracies from model registry (single source) ────────────────
  const agentAccuracies = useMemo(() => {
    const map = { demand: null, supplier: null, inventory: null, logistics: null }
    Object.entries(models).forEach(([key, m]) => {
      if (!m?.metrics) return
      const acc = m.metrics.accuracy ?? m.metrics.r2_score ?? null
      if (acc != null && map[key] !== undefined) {
        map[key] = Math.round(acc * 1000) / 10  // e.g. 0.942 → 94.2
      }
    })
    return map
  }, [models])

  // ── Forecast metrics ─────────────────────────────────────────────────────
  const forecastPeriod     = f.forecast_period     ?? null
  const overallConfidence  = f.overall_confidence  ?? null
  const categoryForecasts  = f.category_forecasts  ?? []
  const highRiskCount      = f.high_risk_count     ?? null
  const mediumRiskCount    = f.medium_risk_count   ?? null
  const agentResults       = f.agent_results       ?? {}

  // ── RCA ──────────────────────────────────────────────────────────────────
  const rcaTypeDist = rcaDashQ.data?.type_distribution ?? []

  // ── Financial exposure (derived from real data only) ─────────────────────
  // Uses: total_orders × avg_sales × late_delivery_rate as proxy for exposure
  // Only computed when all three source values are available from backend
  const financialExposure = useMemo(() => {
    if (totalOrders == null || lateDeliveryPct == null) return null
    // avg order value from dataset summary if available, else null
    const avgOrderVal = s.avg_order_value ?? null
    if (avgOrderVal == null) return null
    return Math.round(totalOrders * (lateDeliveryPct / 100) * avgOrderVal)
  }, [totalOrders, lateDeliveryPct, s.avg_order_value])

  // ── Supplier reliability as percentage ───────────────────────────────────
  const supplierReliabilityPct = avgSupplierReliability != null
    ? Math.round(avgSupplierReliability * 1000) / 10
    : null

  return {
    // Loading states
    isLoading: summaryQ.isLoading || analyticsQ.isLoading,
    isFetching: summaryQ.isFetching || analyticsQ.isFetching,

    // Dataset ground truth
    totalOrders,
    lateDeliveryPct,
    avgShippingDelay,
    avgSupplierReliability,
    supplierReliabilityPct,
    dateRangeStart,
    dateRangeEnd,
    monthlyTrend,
    shippingRisk,
    categoryVolatility,
    riskBreakdown,
    trainingMetrics,
    categories: s.categories ?? [],
    regions: s.regions ?? [],

    // Knowledge Graph
    graphVersion,
    totalNodes,
    totalRels,
    nodeCounts,
    tpkeVersion,
    tpkeEdgeCount,
    tpkeAvgConf,

    // Agent accuracies (single source of truth for all pages)
    agentAccuracies,

    // Forecast
    forecastPeriod,
    overallConfidence,
    categoryForecasts,
    highRiskCount,
    mediumRiskCount,
    agentResults,

    // Financial
    financialExposure,

    // RCA
    rcaTypeDist,

    // Raw query objects (for pages that need more detail)
    summaryQ,
    analyticsQ,
    forecastQ,
    kpisQ,
    graphStatsQ,
    tpkeDashQ,
    tpkeEdgesQ,
    rcaStatsQ,
    rcaDashQ,
    rcaHistoryQ,
    riskDashQ,
    forecastDashQ,
    trendsQ,
    modelsQ,
    networkData,
  }
}

// ─── Global invalidation (call after any upload) ─────────────────────────────

export function useInvalidateAll() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.all })
}
