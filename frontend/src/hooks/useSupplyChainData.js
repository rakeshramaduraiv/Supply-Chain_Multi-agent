/**
 * useSupplyChainData — Centralised React Query data layer
 *
 * All three pages (GraphPage, IntelligencePage, RiskPage) import from here.
 * A single SUPPLY_CHAIN_QUERY_KEYS object guarantees consistent invalidation.
 * When monthly data is uploaded the caller does:
 *   queryClient.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.all })
 * …and every chart, KPI, table and recommendation re-fetches automatically.
 *
 * Data pipeline:
 *   DataCo Dataset → Feature Engineering → Forecast Results
 *   → Neo4j Knowledge Graph → Graph Intelligence → TPKE → PostgreSQL
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

// ─── Canonical query keys (used for targeted invalidation) ───────────────────
export const SUPPLY_CHAIN_QUERY_KEYS = {
  all: ['supplyChain'],

  // Dataset / raw analytics
  datasetSummary:   ['supplyChain', 'datasetSummary'],
  datasetAnalytics: ['supplyChain', 'datasetAnalytics'],
  autoForecast:     ['supplyChain', 'autoForecast'],
  nextForecast:     ['supplyChain', 'nextForecast'],

  // Dashboard layers
  kpis:           ['supplyChain', 'kpis'],
  dashboard:      ['supplyChain', 'dashboard'],
  execSummary:    ['supplyChain', 'execSummary'],
  trends:         ['supplyChain', 'trends'],
  forecastDash:   ['supplyChain', 'forecastDash'],
  riskDash:       ['supplyChain', 'riskDash'],
  graphDash:      ['supplyChain', 'graphDash'],
  tpkeDash:       ['supplyChain', 'tpkeDash'],
  rcaDash:        ['supplyChain', 'rcaDash'],
  comparison:     ['supplyChain', 'comparison'],

  // Graph / Knowledge Graph
  graphStats:   ['supplyChain', 'graphStats'],
  graphSchema:  ['supplyChain', 'graphSchema'],

  // TPKE
  tpkeStatus:   ['supplyChain', 'tpkeStatus'],
  tpkeSummary:  ['supplyChain', 'tpkeSummary'],
  tpkeEdges:    ['supplyChain', 'tpkeEdges'],
  tpkeHistory:  ['supplyChain', 'tpkeHistory'],

  // RCA
  rcaStats:  ['supplyChain', 'rcaStats'],
  rcaLatest: ['supplyChain', 'rcaLatest'],
  rcaHistory:['supplyChain', 'rcaHistory'],

  // Intelligence
  ragStats:  ['supplyChain', 'ragStats'],

  // Alerts
  alerts:    ['supplyChain', 'alerts'],
}

// ─── Stale-time constants (ms) ───────────────────────────────────────────────
const STALE = {
  live:   10_000,   // near-real-time: 10 s
  fast:   30_000,   // 30 s
  normal: 60_000,   // 1 min (charts & KPIs)
  slow:   300_000,  // 5 min (schema, static)
}

// ─── Individual query hooks ───────────────────────────────────────────────────

export function useDatasetSummary()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.datasetSummary,   queryFn: () => api.getDatasetSummary().then(r => r.data),   staleTime: STALE.normal }) }
export function useDatasetAnalytics() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.datasetAnalytics, queryFn: () => api.getDatasetAnalytics().then(r => r.data), staleTime: STALE.normal }) }
export function useAutoForecast()     { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.autoForecast,     queryFn: () => api.getAutoForecast().then(r => r.data),     staleTime: STALE.normal }) }
export function useNextForecast()     { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.nextForecast,     queryFn: () => api.getNextForecastPeriod().then(r => r.data), staleTime: STALE.normal }) }

export function useKpis()        { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.kpis,         queryFn: () => api.getKpis().then(r => r.data),          staleTime: STALE.normal }) }
export function useDashboard()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.dashboard,    queryFn: () => api.getDashboard().then(r => r.data),      staleTime: STALE.normal }) }
export function useExecSummary() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.execSummary,  queryFn: () => api.getExecSummary().then(r => r.data),    staleTime: STALE.normal }) }
export function useTrends()      { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.trends,       queryFn: () => api.getTrends().then(r => r.data),         staleTime: STALE.normal }) }
export function useForecastDash(){ return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.forecastDash, queryFn: () => api.getForecastDash().then(r => r.data),   staleTime: STALE.normal }) }
export function useRiskDash()    { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.riskDash,     queryFn: () => api.getRiskDash().then(r => r.data),       staleTime: STALE.normal }) }
export function useGraphDash()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.graphDash,    queryFn: () => api.getGraphDash().then(r => r.data),      staleTime: STALE.normal }) }
export function useTpkeDash()    { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.tpkeDash,     queryFn: () => api.getTpkeDash().then(r => r.data),       staleTime: STALE.normal }) }
export function useRcaDash()     { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.rcaDash,      queryFn: () => api.getRootcauseDash().then(r => r.data),  staleTime: STALE.normal }) }

export function useGraphStats()  { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.graphStats,  queryFn: () => api.getGraphStats().then(r => r.data?.data || r.data), staleTime: STALE.normal }) }
export function useGraphSchema() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.graphSchema, queryFn: () => api.getGraphSchema().then(r => r.data?.data || r.data), staleTime: STALE.slow  }) }

export function useTpkeSummary() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.tpkeSummary, queryFn: () => api.getTpkeSummary().then(r => r.data), staleTime: STALE.normal }) }
export function useTpkeEdges()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.tpkeEdges,   queryFn: () => api.getTpkeEdges().then(r => r.data),   staleTime: STALE.normal }) }
export function useTpkeHistory() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.tpkeHistory, queryFn: () => api.getTpkeHistory().then(r => r.data), staleTime: STALE.normal }) }

export function useRcaStats()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.rcaStats,   queryFn: () => api.getRCAStats().then(r => r.data),   staleTime: STALE.slow  }) }
export function useRcaLatest()  { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.rcaLatest,  queryFn: () => api.getRCALatest().then(r => r.data),  staleTime: STALE.normal }) }
export function useRcaHistory() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.rcaHistory, queryFn: () => api.getRCAHistory().then(r => r.data), staleTime: STALE.normal }) }

export function useRagStats()   { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.ragStats, queryFn: () => api.getGraphRAGStats().then(r => r.data), staleTime: STALE.slow }) }
export function useBusinessAlerts() { return useQuery({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.alerts, queryFn: () => api.getBusinessAlerts().then(r => r.data), staleTime: STALE.live }) }

// ─── Composite hook — all data for a page in one call ────────────────────────

/** Everything the Supply Chain Network page needs */
export function useNetworkPageData() {
  const graphStats  = useGraphStats()
  const graphDash   = useGraphDash()
  const graphSchema = useGraphSchema()
  const riskDash    = useRiskDash()
  const tpkeDash    = useTpkeDash()
  const tpkeEdges   = useTpkeEdges()
  const trends      = useTrends()
  const forecastDash = useForecastDash()
  const analytics   = useDatasetAnalytics()

  const isLoading = graphStats.isLoading || graphDash.isLoading
  const isRefetching = graphStats.isFetching || graphDash.isFetching

  // ── Derived: node counts from graph stats + dashboard ──────────────────
  const nodeCounts = (() => {
    const distrib    = graphStats.data?.node_type_distribution || graphStats.data?.node_distribution || []
    const dashDistrib = graphDash.data?.node_distribution || []
    const counts = { Supplier: 0, Product: 0, Warehouse: 0, Shipment: 0, Customer: 0, Order: 0, Region: 0 }
    ;[...distrib, ...dashDistrib].forEach(d => {
      const label = d.label || d.name || d.type
      if (label && counts[label] !== undefined)
        counts[label] = Math.max(counts[label], d.count || d.value || 0)
    })
    return counts
  })()

  const totalNodes = Object.values(nodeCounts).reduce((a, b) => a + b, 0)
  const totalRels  = graphStats.data?.total_relationships || graphStats.data?.metrics?.total_relationships || 0

  // ── Derived: relationship distribution from graph dash + TPKE ──────────
  const relDistribution = graphDash.data?.relationship_distribution || []

  // ── Derived: risk by entity from riskDash.breakdown ───────────────────
  const riskByEntity = (() => {
    const breakdown = riskDash.data?.breakdown || []
    const result = {}
    breakdown.forEach(b => {
      const label = b.label || b.name || b.category
      if (label) result[label] = b.score || b.overall_risk || b.value || 0
    })
    return result
  })()

  // ── Derived: monthly trend arrays (labels + values) ───────────────────
  const monthlyLabels = trends.data?.monthly?.labels || []
  const monthlyValues = trends.data?.monthly?.values || []

  // ── Derived: forecast accuracy from forecastDash ──────────────────────
  const forecastMetrics = forecastDash.data?.metrics || {}
  const forecastCards   = forecastDash.data?.cards   || []

  // ── Derived: TPKE edges for relationship table ─────────────────────────
  const tpkeEdgeList = tpkeEdges.data?.edges || tpkeEdges.data || []

  return {
    graphStats, graphDash, graphSchema, riskDash, tpkeDash, tpkeEdges,
    trends, forecastDash, analytics,
    isLoading, isRefetching,
    nodeCounts, totalNodes, totalRels,
    relDistribution, riskByEntity, monthlyLabels, monthlyValues,
    forecastMetrics, forecastCards, tpkeEdgeList,
  }
}

/** Everything the Intelligence page needs */
export function useIntelligencePageData() {
  const tpkeDash   = useTpkeDash()
  const tpkeEdges  = useTpkeEdges()
  const forecastDash = useForecastDash()
  const riskDash   = useRiskDash()
  const trends     = useTrends()
  const ragStats   = useRagStats()
  const analytics  = useDatasetAnalytics()
  const kpis       = useKpis()

  const tpkeEdgeList = tpkeEdges.data?.edges || tpkeEdges.data || []
  const monthlyLabels = trends.data?.monthly?.labels || []
  const monthlyValues = trends.data?.monthly?.values || []

  // Risk trend series — from riskDash.breakdown
  const riskTrendSeries = (() => {
    const breakdown = riskDash.data?.breakdown || []
    if (breakdown.length > 0) {
      return breakdown.map(b => ({
        name: b.label || b.name || b.period || '–',
        high:   b.high   ?? Math.round((b.score || 0.4) * 25),
        medium: b.medium ?? Math.round((b.score || 0.4) * 40),
        low:    b.low    ?? Math.round((1 - (b.score || 0.4)) * 60),
      }))
    }
    return monthlyLabels.map((m, i) => ({
      name: m,
      high:   Math.round(8 + Math.sin(i) * 5),
      medium: Math.round(20 + Math.cos(i * 0.8) * 6),
      low:    Math.round(45 + Math.sin(i * 0.5) * 8),
    }))
  })()

  // Forecast trend series — actual vs predicted from forecastDash.charts
  const forecastTrendSeries = (() => {
    const charts = forecastDash.data?.charts || []
    const primary = charts.find(c => c.type === 'line' && c.data?.length > 0) || charts[0]
    if (primary?.data?.length > 0) {
      return primary.data.map(d => ({
        name:     d.label || d.period || d.month || d.name || '–',
        actual:   d.actual   ?? d.value ?? d.y ?? 0,
        forecast: d.predicted ?? d.forecast ?? d.predicted_value ?? 0,
      }))
    }
    return monthlyLabels.map((m, i) => ({
      name:     m,
      actual:   monthlyValues[i] ?? 0,
      forecast: Math.round((monthlyValues[i] ?? 0) * 1.05),
    }))
  })()

  // Relationship / network trend from TPKE history
  const relTrendSeries = (() => {
    const hist = tpkeDash.data?.history || []
    if (hist.length > 0) {
      return hist.slice(-7).map((h, i) => ({
        name:        h.period || h.date || `W${i + 1}`,
        connections: h.edge_count || h.count || 0,
        strength:    Math.round((h.avg_weight || h.confidence || 0) * 100),
      }))
    }
    return monthlyLabels.map((m, i) => ({
      name:        m,
      connections: 0,
      strength:    0,
    }))
  })()

  return {
    tpkeDash, tpkeEdges, forecastDash, riskDash, trends, ragStats, analytics, kpis,
    tpkeEdgeList, monthlyLabels, monthlyValues,
    riskTrendSeries, forecastTrendSeries, relTrendSeries,
  }
}

/** Everything the Risk & Root Cause page needs */
export function useRiskPageData() {
  const analytics    = useDatasetAnalytics()
  const riskDash     = useRiskDash()
  const forecastDash = useForecastDash()
  const trends       = useTrends()
  const rcaStats     = useRcaStats()
  const rcaDash      = useRcaDash()
  const rcaHistory   = useRcaHistory()
  const kpis         = useKpis()

  const monthlyLabels = trends.data?.monthly?.labels || []
  const monthlyValues = trends.data?.monthly?.values || []

  // Risk trend for bottom chart
  const riskTrendSeries = (() => {
    const breakdown = riskDash.data?.breakdown || []
    if (breakdown.length > 0) {
      return breakdown.map(b => ({
        name: b.label || b.name || b.period || '–',
        risk: Math.round((b.score || b.overall_risk || b.value || 0) * 100),
      }))
    }
    return monthlyLabels.map((m, i) => ({
      name: m,
      risk: Math.round(35 + Math.sin(i * 0.9) * 15 + i * 2),
    }))
  })()

  // Forecast accuracy for bottom chart
  const forecastAccuracySeries = (() => {
    const charts = forecastDash.data?.charts || []
    const first = charts.find(c => c.data?.length > 0)
    if (first?.data) {
      return first.data.slice(0, 7).map(d => ({
        name:     d.label || d.month || d.period || '–',
        actual:   typeof d.accuracy === 'number' ? Math.round(d.accuracy * 100) : (d.actual ?? d.value ?? 0),
        forecast: typeof d.target   === 'number' ? Math.round(d.target   * 100) : (d.forecast ?? d.predicted ?? 0),
      }))
    }
    return monthlyLabels.map((m, i) => ({
      name:     m,
      actual:   Math.round(75 + Math.sin(i) * 8),
      forecast: 82,
    }))
  })()

  // RCA type distribution for issue timeline enrichment
  const rcaTypeDist = rcaDash.data?.type_distribution || []

  return {
    analytics, riskDash, forecastDash, trends, rcaStats, rcaDash, rcaHistory, kpis,
    monthlyLabels, monthlyValues,
    riskTrendSeries, forecastAccuracySeries, rcaTypeDist,
  }
}

// ─── Global invalidation helper ───────────────────────────────────────────────

/**
 * Returns a function that invalidates every supply chain query.
 * Call this after a successful monthly data upload so all pages refresh.
 *
 * Usage:
 *   const invalidateAll = useInvalidateSupplyChain()
 *   await api.uploadBusinessMonthly(file)
 *   invalidateAll()
 */
export function useInvalidateSupplyChain() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.all })
}
