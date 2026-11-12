/**
 * ForecastPage.jsx
 */
import { useState, useMemo, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw, BarChart2, CheckCircle, Zap, Cpu, Rocket, AlertTriangle, Factory,
  Warehouse, Truck, Users, ArrowUpRight, ShieldCheck, Activity,
  Play, GitBranch, Search,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ComposedChart, LineChart, Line, Legend, PieChart, Pie, Cell,
} from 'recharts'
import { api, createWebSocket } from '../api/client'
import { useToast } from '../components/ui/Toast'
import styles from './ForecastPage.module.css'
import { useSharedParams } from '../hooks/useSharedParams'
import CycleStepper from '../components/forecast/CycleStepper'
import ValidationPanel from '../components/forecast/ValidationPanel'

const ChartTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 8, padding: '8px 12px', fontSize: 11, boxShadow: '0 4px 16px rgba(0,0,0,.25)' }}>
      <div style={{ fontWeight: 600, color: 'var(--tp)', marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color || p.stroke, flexShrink: 0 }} />
          <span style={{ color: 'var(--ts)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--tp)', fontVariantNumeric: 'tabular-nums' }}>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  )
}

const round = (n, d = 1) => Number(Math.round(n + 'e' + d) + 'e-' + d)

export default function ForecastPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const { navigateToPage } = useSharedParams()

  const readLS  = (k, fb) => { try { const v = localStorage.getItem(k); return v != null ? JSON.parse(v) : fb } catch { return fb } }
  const writeLS = (k, v)  => { try { localStorage.setItem(k, JSON.stringify(v)) } catch {} }

  const [activeTab, _setActiveTab] = useState(() => readLS('amasci_cycle_tab', 'intelligence'))
  const setActiveTab = (v) => { _setActiveTab(v); writeLS('amasci_cycle_tab', v) }

  const [cycleStep, _setCycleStep]                     = useState(() => readLS('amasci_cycle_step', 1))
  const [cycleMonth, _setCycleMonth]                   = useState(() => readLS('amasci_cycle_month', ''))
  const [cycleTrainedUntil, _setCycleTrainedUntil]     = useState(() => readLS('amasci_cycle_trained_until', '2017-09'))
  const [cycleActualsUploaded, _setCycleActualsUploaded] = useState(false)
  const [cycleModelRetrained,  _setCycleModelRetrained]  = useState(false)

  const setCycleStep         = (v) => { _setCycleStep(v);         writeLS('amasci_cycle_step', v) }
  const setCycleMonth        = (v) => { _setCycleMonth(v);        writeLS('amasci_cycle_month', v) }
  const setCycleTrainedUntil = (v) => { _setCycleTrainedUntil(v); writeLS('amasci_cycle_trained_until', v) }
  const setCycleActualsUploaded = (v) => _setCycleActualsUploaded(v)

  const [cycleUploadResult, setCycleUploadResult] = useState(null)
  const [actualsFile, setActualsFile]             = useState(null)

  const [completedCycles, _setCompletedCycles] = useState(() => {
    try { return JSON.parse(localStorage.getItem('amasci_completed_cycles') || '[]') } catch { return [] }
  })
  const setCompletedCycles = (fn) => {
    _setCompletedCycles(prev => {
      const next = typeof fn === 'function' ? fn(prev) : fn
      try { localStorage.setItem('amasci_completed_cycles', JSON.stringify(next)) } catch {}
      return next
    })
  }

  const [uploadHistory,      setUploadHistory]      = useState([])
  const [isIngestingActuals, setIsIngestingActuals] = useState(false)
  const [isIssuingForecast,  setIsIssuingForecast]  = useState(false)
  const [catSearch,          setCatSearch]          = useState('')
  const [catRegionFilter,    setCatRegionFilter]    = useState('All')
  const [catRiskFilter,      setCatRiskFilter]      = useState('All')
  const [diagSearch,         setDiagSearch]         = useState('')
  const [diagAgentFilter,    setDiagAgentFilter]    = useState('All')
  const [diagMatchFilter,    setDiagMatchFilter]    = useState('All')

  // WebSocket
  useEffect(() => {
    let ws
    try {
      ws = createWebSocket((msg) => {
        const ev = msg?.event || ''
        if (['stage_update','Actual Uploaded','Knowledge Graph Updated','cycle_complete'].includes(ev)) {
          refetchCycle()
          qc.invalidateQueries(['supplyChain', 'autoForecast'])
        }
      })
    } catch {}
    return () => { try { ws?.close() } catch {} }
  }, []) // eslint-disable-line

  // Session reconciliation
  useEffect(() => {
    const key = 'amasci_session_active'
    if (!sessionStorage.getItem(key)) {
      localStorage.removeItem('amasci_cycle_actuals_uploaded')
      localStorage.removeItem('amasci_cycle_upload_result')
      localStorage.removeItem('amasci_cycle_tab')
      sessionStorage.setItem(key, '1')
    }
    api.getDatasetCoverage().then(r => {
      const sig = JSON.stringify({ base: r?.data?.base_row_count, inc: r?.data?.increment_count, latest: r?.data?.latest_date })
      const stored = localStorage.getItem('amasci_coverage_sig')
      if (stored && stored !== sig) { localStorage.removeItem('amasci_cycle_step'); _setCycleStep(1); _setCycleActualsUploaded(false) }
      localStorage.setItem('amasci_coverage_sig', sig)
    }).catch(() => {})
  }, [])

  // Backend restart detection
  useEffect(() => {
    api.live().then(r => {
      const sid = r?.data?.session_id
      if (!sid) return
      const stored = localStorage.getItem('amasci_backend_session')
      if (stored && stored !== sid) {
        ['amasci_cycle_step','amasci_cycle_month','amasci_cycle_trained_until',
         'amasci_cycle_actuals_uploaded','amasci_cycle_upload_result','amasci_cycle_tab',
         'amasci_rca_focus','amasci_graph_focus','amasci_forecast_incidents','amasci_completed_cycles',
        ].forEach(k => localStorage.removeItem(k))
        sessionStorage.removeItem('amasci_session_active')
        _setCycleStep(1); _setCycleMonth(''); _setCycleTrainedUntil('2017-09')
        _setCycleActualsUploaded(false); _setCycleModelRetrained(false)
        setCycleUploadResult(null); _setCompletedCycles([]); setUploadHistory([])
        _setActiveTab('intelligence')
        toast.info('Backend restarted — lifecycle reset')
      }
      localStorage.setItem('amasci_backend_session', sid)
    }).catch(() => {})
  }, [])

  // Queries
  const { data: forecastRaw,  isLoading: loadingForecast } = useQuery({
    queryKey: ['supplyChain', 'autoForecast'],
    queryFn:  () => api.getAutoForecast().then(r => r.data),
    staleTime: 30_000, refetchInterval: 60_000,
  })
  const { data: analyticsRaw } = useQuery({
    queryKey: ['supplyChain', 'datasetAnalytics'],
    queryFn:  () => api.getDatasetAnalytics().then(r => r.data),
    staleTime: 30_000,
  })
  const { data: summaryRaw } = useQuery({
    queryKey: ['supplyChain', 'datasetSummary'],
    queryFn:  () => api.getDatasetSummary().then(r => r.data),
    staleTime: 30_000,
  })
  const { data: modelsRaw } = useQuery({
    queryKey: ['supplyChain', 'latestModels'],
    queryFn:  () => api.getLatestModels().then(r => r.data),
    staleTime: 60_000,
  })
  const { data: graphStatsRaw } = useQuery({
    queryKey: ['supplyChain', 'graphStats'],
    queryFn:  () => api.getGraphStats().then(r => r.data),
    staleTime: 60_000,
  })
  const { data: tpkeStatusRaw } = useQuery({
    queryKey: ['supplyChain', 'tpkeStatus'],
    queryFn:  () => api.getTpkeStatus().then(r => r.data),
    staleTime: 60_000,
  })
  const demandFI = useQuery({
    queryKey: ['supplyChain', 'featureImportance', 'demand'],
    queryFn:  () => api.getFeatureImportance('demand').then(r => r.data),
    staleTime: 120_000,
  })
  const supplierFI = useQuery({
    queryKey: ['supplyChain', 'featureImportance', 'supplier'],
    queryFn:  () => api.getFeatureImportance('supplier').then(r => r.data),
    staleTime: 120_000,
  })
  const logisticsFI = useQuery({
    queryKey: ['supplyChain', 'featureImportance', 'logistics'],
    queryFn:  () => api.getFeatureImportance('logistics').then(r => r.data),
    staleTime: 120_000,
  })
  const { data: cycleState, isLoading: isCycleLoading, refetch: refetchCycle } = useQuery({
    queryKey: ['supplyChain', 'cycleState'],
    queryFn:  () => api.getCycleState().then(r => r.data),
    staleTime: 5_000, refetchInterval: 10_000,
  })
  const { data: availablePeriodsRaw } = useQuery({
    queryKey: ['supplyChain', 'availablePeriods'],
    queryFn:  () => api.getAvailablePeriods().then(r => r.data),
    staleTime: 60_000,
  })
  const availablePeriods = availablePeriodsRaw?.periods || []

  const errorDiagQuery = useQuery({
    queryKey: ['supplyChain', 'errorDiagnostics', cycleMonth],
    queryFn:  () => api.getErrorDiagnostics(cycleMonth).then(r => r.data),
    staleTime: 30_000, refetchInterval: 60_000,
  })

  // Sync cycleMonth from backend
  useEffect(() => {
    if (cycleState?.current_period) setCycleMonth(cycleState.current_period)
    else if (forecastRaw?.forecast_period) setCycleMonth(forecastRaw.forecast_period)
  }, [cycleState?.current_period, forecastRaw?.forecast_period])

  // Handlers
  const handleIssueForecast = async (period) => {
    setIsIssuingForecast(true)
    try {
      await api.issueForecast(period)
      await refetchCycle()
      qc.invalidateQueries(['supplyChain', 'autoForecast'])
      toast.success('Forecast issued for ' + period)
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Forecast failed: ' + e.message)
    } finally { setIsIssuingForecast(false) }
  }

  const handleResetCycle = async () => {
    try {
      await api.resetCycle()
      await refetchCycle()
      qc.invalidateQueries(['supplyChain'])
      toast.success('Cycle reset')
    } catch (e) { toast.error('Reset failed: ' + e.message) }
  }

  const handleIngestSyntheticMonth = (periodStr, csvFile) => {
    if (!csvFile) { toast.error('Please select a CSV file to upload actuals.'); return }
    setIsIngestingActuals(true)

    const handleResult = (res) => {
      const data = res?.data || {}
      const recs = data.comparison_records || []
      const matchedRecs   = recs.filter(r => r.matched && r.actual_value != null)
      const forecastRecs  = recs.filter(r => r.forecast_value != null)
      const totalForecast = forecastRecs.length > 0 ? forecastRecs.reduce((s, r) => s + r.forecast_value, 0) : null
      const totalActual   = matchedRecs.length  > 0 ? matchedRecs.reduce((s, r) => s + r.actual_value, 0)   : null
      const validDev = matchedRecs.filter(r => r.deviation_pct != null && r.actual_value > 0)
      const mape = validDev.length > 0
        ? validDev.reduce((s, r) => s + Math.abs(r.forecast_value - r.actual_value) / r.actual_value * 100, 0) / validDev.length
        : null
      const devSummary = data.deviation_summary || {}
      const result = {
        records_loaded:    data.records_loaded ?? recs.length,
        records_matched:   data.records_matched ?? matchedRecs.length,
        mape_val:          mape != null ? parseFloat(mape.toFixed(2)) : null,
        zero_actual_count: matchedRecs.filter(r => r.actual_value === 0).length,
        forecast_coverage: { total: forecastRecs.length, of: recs.length },
        actual_coverage:   { total: matchedRecs.length,  of: recs.length },
        deviation_summary: {
          within_threshold: devSummary.within_threshold ?? 0,
          minor_deviation:  devSummary.minor_deviation  ?? 0,
          major_deviation:  devSummary.major_deviation  ?? 0,
        },
        period: periodStr,
        comparison_records: recs,
        chart_point: { period: periodStr, actual: totalActual, forecast: totalForecast },
      }
      setCycleUploadResult(result)
      setCycleActualsUploaded(true)
      setIsIngestingActuals(false)
      setCompletedCycles(prev => {
        const filtered = prev.filter(c => c.period !== periodStr)
        const forecastOrders = categoryForecasts.filter(c => c.order_count != null).reduce((s, c) => s + c.order_count, 0) || null
        return [...filtered, { ...result.chart_point, forecast_orders: forecastOrders || result.chart_point.forecast, actual_orders: result.records_loaded > 0 ? result.records_loaded : null }]
      })
      const mapeStr = mape != null ? `${mape.toFixed(2)}%` : '—'
      const newIncidents = recs
        .filter(r => r.deviation_pct != null && !isNaN(parseFloat(r.deviation_pct)) && Math.abs(parseFloat(r.deviation_pct)) > 5)
        .map(r => ({
          id: `forecast_deviation_${periodStr}_${r.entity_id?.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
          name: `Forecast Deviation: ${r.entity_id}`, type: 'Product', period: periodStr,
          periodLabel: availablePeriods.find(m => m.period === periodStr)?.label || periodStr,
          risk: r.deviation_pct != null ? `${Math.abs(parseFloat(r.deviation_pct)).toFixed(1)}%` : '—',
          riskVal: r.deviation_pct != null ? Math.abs(parseFloat(r.deviation_pct)) / 100 : null,
          severity: Math.abs(parseFloat(r.deviation_pct)) > 8 ? 'High' : 'Medium',
          impact: 'Medium', confidence: mapeStr,
          financialLoss: r.forecast_value != null && r.actual_value != null ? Math.round(Math.abs(r.forecast_value - r.actual_value) * 45) : 0,
          affectedOrders: r.forecast_value != null && r.actual_value != null ? Math.round(Math.abs(r.forecast_value - r.actual_value)) : 0,
          expectedDelay: 0.8, region: r.entity_id?.match(/\((.+)\)/)?.[1] || 'Global',
          warehouse: 'Zone 1', bu: 'Forecasting', status: 'Open RCA',
          customers: r.forecast_value != null && r.actual_value != null ? Math.round(Math.abs(r.forecast_value - r.actual_value) * 0.4) : 0,
          products: 1, forecastDrop: Math.abs(parseFloat(r.deviation_pct)),
          startedTime: `${periodStr}-01 00:00`, affectedSupplier: r.responsible_agent || 'Demand Agent',
          affectedWarehouse: 'Warehouse Zone 1', businessCriticality: 'Medium Priority',
          graphConfidence: mapeStr, predictionSource: `Forecast Cycle — ${periodStr}`,
          timeSinceDetection: `Uploaded ${periodStr} Actuals`, _fromForecast: true,
        }))
      if (newIncidents.length > 0) {
        const existing = JSON.parse(localStorage.getItem('amasci_forecast_incidents') || '[]')
        localStorage.setItem('amasci_forecast_incidents', JSON.stringify([...newIncidents, ...existing.filter(i => !newIncidents.some(n => n.id === i.id))]))
        window.dispatchEvent(new CustomEvent('amasci:forecast_incidents_updated'))
      }
      setUploadHistory(prev => [{ period: periodStr, records: result.records_loaded, status: result.records_matched === 0 ? 'Skipped' : 'Validated', mape: mapeStr, coverage: `${result.forecast_coverage.total}/${result.forecast_coverage.of}`, timestamp: new Date().toLocaleString() }, ...prev])
      toast.success(`Actuals for ${periodStr} ingested — ${matchedRecs.length} categories matched`)
      qc.invalidateQueries({ queryKey: ['supplyChain'] })
      refetchCycle()
      setCycleStep(3)
    }

    api.uploadActual(csvFile, periodStr)
      .then(res => handleResult(res))
      .catch(err => {
        setIsIngestingActuals(false)
        const is409 = err?.status === 409
        toast.error(is409 ? `Upload blocked: ${err.message}` : `Upload failed: ${err.message}`)
      })
  }

  // Derived data
  const f          = forecastRaw  || {}
  const analytics  = analyticsRaw || {}
  const graphStats = graphStatsRaw?.data || graphStatsRaw || {}
  const tpkeStatus = tpkeStatusRaw?.data || tpkeStatusRaw || {}

  const overallConf        = (f.overall_confidence != null && !isNaN(f.overall_confidence)) ? f.overall_confidence : null
  const forecastPeriod     = f.forecast_period || ''
  const activeGraphVersion = graphStats.graph_version || null
  const activeTpkeVersion  = tpkeStatus.version || null

  const categoryForecasts = useMemo(() => {
    const raw = f.category_forecasts || []
    if (!raw.length) return []
    return [...raw].sort((a, b) => (b.combined_risk || 0) - (a.combined_risk || 0)).map(c => ({
      category:          c.category,
      region:            c.region,
      predicted_demand:  c.predicted_demand  != null ? Math.round(c.predicted_demand)  : null,
      predicted_revenue: c.predicted_revenue != null ? Math.round(c.predicted_revenue) : null,
      prediction_unit:   'units',
      late_delivery_risk:c.supplier_risk  != null ? c.supplier_risk  : null,
      stock_risk:        c.logistics_risk != null ? c.logistics_risk : null,
      avg_shipping_days: c.demand_risk    != null ? c.demand_risk    : null,
      combined_risk:     c.combined_risk  != null ? c.combined_risk  : null,
      order_count:       c.order_count    != null ? c.order_count    : null,
    }))
  }, [f.category_forecasts])

  const monthlyTrend = analytics.monthly_trend || []

  const formatFI = (fiData) => {
    const list = fiData?.feature_importances || fiData?.features || []
    if (!list.length) return []
    const sorted = [...list].filter(i => { const v = i.importance ?? i.score; return v != null && !isNaN(v) }).sort((a, b) => (b.importance ?? b.score) - (a.importance ?? a.score)).slice(0, 5)
    if (sorted.length < 2) return []
    const sum = sorted.reduce((acc, i) => acc + (i.importance ?? i.score), 0)
    if (sum === 0) return []
    return sorted.map(i => ({ name: (i.feature || i.name || '').replace(/_/g, ' '), pct: round((i.importance ?? i.score) / sum * 100, 1) }))
  }

  const demandFeatures    = useMemo(() => formatFI(demandFI.data),    [demandFI.data])
  const supplierFeatures  = useMemo(() => formatFI(supplierFI.data),  [supplierFI.data])
  const logisticsFeatures = useMemo(() => formatFI(logisticsFI.data), [logisticsFI.data])

  const buildMonthSequence = (endPeriod, count = 12) => {
    if (!endPeriod?.includes('-')) return []
    let [y, m] = endPeriod.split('-').map(Number)
    if (!y || !m || isNaN(y) || isNaN(m)) return []
    const months = []
    for (let i = 0; i < count; i++) {
      months.unshift(`${y}-${String(m).padStart(2, '0')}`)
      m -= 1; if (m === 0) { m = 12; y -= 1 }
    }
    return months
  }

  const historicalForecastSeries = useMemo(() => {
    const trendMap = {}
    ;(monthlyTrend || []).forEach(m => { trendMap[m.period] = m.orders || 0 })
    const forecastOrderCount = categoryForecasts.filter(c => c.order_count != null).reduce((s, c) => s + c.order_count, 0) || 0
    const ingestedMap = {}
    completedCycles.forEach(cp => { ingestedMap[cp.period] = { forecast_orders: cp.forecast_orders ?? cp.forecast ?? null, actual_orders: cp.actual_orders ?? cp.actual ?? null } })
    if (cycleUploadResult?.period) {
      const p = cycleUploadResult.period
      ingestedMap[p] = { forecast_orders: forecastOrderCount > 0 ? forecastOrderCount : (ingestedMap[p]?.forecast_orders ?? null), actual_orders: cycleUploadResult.records_loaded > 0 ? cycleUploadResult.records_loaded : null }
    } else if (cycleMonth && forecastOrderCount > 0) {
      ingestedMap[cycleMonth] = { forecast_orders: forecastOrderCount, actual_orders: ingestedMap[cycleMonth]?.actual_orders ?? null }
    }
    return buildMonthSequence(cycleMonth, 12).map(period => ({
      period,
      historical: trendMap[period] ?? null,
      forecast:   ingestedMap[period]?.forecast_orders ?? null,
      actual:     ingestedMap[period]?.actual_orders   ?? null,
    }))
  }, [monthlyTrend, cycleUploadResult, completedCycles, cycleMonth, categoryForecasts])

  const confidenceTimeline = useMemo(() => {
    const trendMap = {}
    if (cycleUploadResult?.mape_val != null && overallConf != null) {
      const valConf = Math.max(0, Math.min(100, parseFloat((100 - cycleUploadResult.mape_val).toFixed(1))))
      trendMap[cycleUploadResult.period] = { prediction_confidence: round(overallConf * 100, 1), validation_confidence: valConf, rolling_average: round((overallConf * 100 + valConf) / 2, 1) }
    }
    return buildMonthSequence(cycleMonth, 12).map(period => {
      const pt = trendMap[period]
      return { month: period, prediction_confidence: pt?.prediction_confidence ?? null, validation_confidence: pt?.validation_confidence ?? null, rolling_average: pt?.rolling_average ?? null }
    })
  }, [overallConf, cycleUploadResult, cycleMonth])

  const deviationData = useMemo(() => {
    const d = cycleUploadResult?.deviation_summary
    if (!d) return [{ name: 'Within Threshold (<10%)', value: 0, color: '#00b894' }, { name: 'Minor Deviation (10-25%)', value: 0, color: '#f59e0b' }, { name: 'Major Deviation (>25%)', value: 0, color: '#d63031' }]
    return [{ name: 'Within Threshold (<10%)', value: d.within_threshold || 0, color: '#00b894' }, { name: 'Minor Deviation (10-25%)', value: d.minor_deviation || 0, color: '#f59e0b' }, { name: 'Major Deviation (>25%)', value: d.major_deviation || 0, color: '#d63031' }]
  }, [cycleUploadResult])

  const agentAccuracyData = useMemo(() => {
    const compRecs = cycleUploadResult?.comparison_records || []
    if (!compRecs.length) return [{ name: 'Demand Agent', accuracy: null, color: 'var(--blue)' }, { name: 'Supplier Agent', accuracy: null, color: '#e67e22' }, { name: 'Logistics Agent', accuracy: null, color: '#d63031' }]
    const agMap = { 'Demand Agent': [], 'Supplier Agent': [], 'Logistics Agent': [] }
    compRecs.forEach(r => {
      const agent = r.responsible_agent || 'Demand Agent'
      if (r.deviation_pct != null && !isNaN(parseFloat(r.deviation_pct)) && agMap[agent]) agMap[agent].push(Math.max(0, Math.min(100, 100 - Math.abs(parseFloat(r.deviation_pct)))))
    })
    return [
      { name: 'Demand Agent',    accuracy: agMap['Demand Agent'].length   > 0 ? round(agMap['Demand Agent'].reduce((a,b)=>a+b,0)/agMap['Demand Agent'].length, 1)   : null, color: 'var(--blue)' },
      { name: 'Supplier Agent',  accuracy: agMap['Supplier Agent'].length > 0 ? round(agMap['Supplier Agent'].reduce((a,b)=>a+b,0)/agMap['Supplier Agent'].length, 1) : null, color: '#e67e22' },
      { name: 'Logistics Agent', accuracy: agMap['Logistics Agent'].length> 0 ? round(agMap['Logistics Agent'].reduce((a,b)=>a+b,0)/agMap['Logistics Agent'].length,1): null, color: '#d63031' },
    ]
  }, [cycleUploadResult])

  const errorDiagnostics = useMemo(() => {
    const recs = cycleUploadResult?.comparison_records || []
    if (cycleActualsUploaded && recs.length > 0) {
      return recs.map(r => {
        const fVal = r.forecast_value, aVal = r.actual_value, unit = r.actual_unit || 'units'
        const diff = (fVal != null && aVal != null) ? aVal - fVal : null
        const pct  = r.deviation_pct
        return {
          category: r.entity_id,
          predicted: fVal != null ? `${Number(fVal).toLocaleString()} ${unit}` : '—',
          actual:    aVal != null ? `${Number(aVal).toLocaleString()} ${unit}` : '—',
          diff: diff != null && pct != null ? `${diff >= 0 ? '+' : ''}${Number(diff).toFixed(0)} (${pct}%)` : '—',
          reason: r.reason || (r.matched ? 'Matched' : 'Not found in uploaded file'),
          responsible_agent: r.responsible_agent || 'Demand Agent',
          root_cause: r.matched ? `Actual ${aVal != null ? Number(aVal).toLocaleString() : '—'} ${unit} vs forecast ${fVal != null ? Number(fVal).toLocaleString() : '—'} ${unit}` : `No actuals for ${r.entity_id}`,
          matched: r.matched, n_rows: r.n_rows, n_unparsed: r.n_unparsed,
        }
      })
    }
    const apiDiag = errorDiagQuery.data?.diagnostics || []
    if (apiDiag.length > 0) return apiDiag.map(d => ({ category: `${d.category} (${d.region})`, predicted: d.predicted_demand != null ? `${Number(d.predicted_demand).toLocaleString()} units` : '—', actual: '—', diff: '—', reason: 'Ingest actuals in Step 2 to see real deviation', responsible_agent: d.responsible_agent || 'Demand Agent', root_cause: 'Awaiting actual data ingestion', matched: false, n_rows: 0, n_unparsed: 0 }))
    if (categoryForecasts.length > 0) return categoryForecasts.map((cat, idx) => ({ category: `${cat.category} (${cat.region})`, predicted: cat.predicted_demand != null ? `${Number(cat.predicted_demand).toLocaleString()} ${cat.prediction_unit || 'units'}` : '—', actual: '—', diff: '—', reason: cat.predicted_demand != null ? 'Ingest actuals in Step 2 to see real deviation' : 'No forecast generated', responsible_agent: ['Logistics Agent','Supplier Agent','Demand Agent'][idx % 3], root_cause: 'Awaiting actual data ingestion', matched: false, n_rows: 0, n_unparsed: 0 }))
    return []
  }, [cycleActualsUploaded, cycleUploadResult, errorDiagQuery.data, categoryForecasts])

  const cats = categoryForecasts
  const totalDemand  = cats.filter(c => c.predicted_demand != null).reduce((s,c) => s + c.predicted_demand, 0)
  const totalRevenue = cats.filter(c => c.predicted_revenue != null).reduce((s,c) => s + c.predicted_revenue, 0)
  const validLate    = cats.filter(c => c.late_delivery_risk != null)
  const avgLateRisk  = validLate.length > 0 ? validLate.reduce((s,c) => s + c.late_delivery_risk, 0) / validLate.length : null
  const validShip    = cats.filter(c => c.avg_shipping_days != null)
  const avgShipDays  = validShip.length > 0 ? validShip.reduce((s,c) => s + c.avg_shipping_days, 0) / validShip.length : null
  const highRisk     = cats.filter(c => (c.combined_risk||0) >= 0.65).length
  const medRisk      = cats.filter(c => (c.combined_risk||0) >= 0.35 && (c.combined_risk||0) < 0.65).length
  const lowRisk      = cats.filter(c => (c.combined_risk||0) < 0.35).length
  const demandConf   = overallConf != null ? round(overallConf * 100, 1) : null
  const ingestedTotal    = cycleUploadResult?.chart_point?.actual ?? null
  const ingestedForecast = cycleUploadResult?.chart_point?.forecast ?? null

  const allRegions = useMemo(() => { const s = new Set(cats.map(c => c.region).filter(Boolean)); return ['All', ...Array.from(s).sort()] }, [cats])

  const filteredCategoryForecasts = useMemo(() => cats.filter(c => {
    if (catRegionFilter !== 'All' && c.region !== catRegionFilter) return false
    if (catRiskFilter === 'High'   && (c.combined_risk || 0) < 0.65) return false
    if (catRiskFilter === 'Medium' && ((c.combined_risk || 0) < 0.35 || (c.combined_risk || 0) >= 0.65)) return false
    if (catRiskFilter === 'Low'    && (c.combined_risk || 0) >= 0.35) return false
    if (catSearch.trim()) { const q = catSearch.toLowerCase(); return c.category?.toLowerCase().includes(q) || c.region?.toLowerCase().includes(q) }
    return true
  }), [cats, catSearch, catRegionFilter, catRiskFilter])

  const filteredDiagnostics = useMemo(() => errorDiagnostics.filter(d => {
    if (diagAgentFilter !== 'All' && d.responsible_agent !== diagAgentFilter) return false
    if (diagMatchFilter === 'Matched'   && !d.matched) return false
    if (diagMatchFilter === 'Unmatched' &&  d.matched) return false
    if (diagSearch.trim()) { const q = diagSearch.toLowerCase(); return d.category?.toLowerCase().includes(q) || d.responsible_agent?.toLowerCase().includes(q) }
    return true
  }), [errorDiagnostics, diagAgentFilter, diagMatchFilter, diagSearch])

  return (
    <div className="page active" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* HEADER */}
      <div className={styles.headerBand}>
        <div className={styles.headerTop}>
          <div>
            <div className={styles.headerTitle}>
              <Rocket size={20} style={{ color: '#60a5fa' }} />
              Enterprise Decision Intelligence &amp; Forecasting Center
            </div>
            <div className={styles.headerSub}>
              DataCo Dataset &middot; {summaryRaw?.date_range_start?.slice(0,7) || 'Jan 2015'} &ndash; {summaryRaw?.date_range_end?.slice(0,7) || 'Sep 2017'} Training Window &middot; Multi-Agent TPKE Learning Loop
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className={`${styles.tabBtn} ${activeTab === 'intelligence' ? styles.tabActive : ''}`} onClick={() => setActiveTab('intelligence')}>
              <Cpu size={13} /> Decision Intelligence
            </button>
            <button className={`${styles.tabBtn} ${activeTab === 'validation' ? styles.tabActive : ''}`} onClick={() => setActiveTab('validation')}>
              <ShieldCheck size={13} /> Validation &amp; Diagnostics
            </button>
          </div>
        </div>
        <div className={styles.executiveGrid}>
          {[
            { label: 'Forecast Period',  val: forecastPeriod || '—',                                          color: '#60a5fa' },
            { label: 'Cycle Status',     val: 'Active',                                                        color: '#00b894' },
            { label: 'Confidence',       val: overallConf != null ? `${(overallConf*100).toFixed(1)}%` : '—', color: '#00b894' },
            { label: 'Graph Version',    val: activeGraphVersion || '—' },
            { label: 'TPKE Version',     val: activeTpkeVersion  || '—' },
            { label: 'Agent Status',     val: 'Active',                                                        color: '#00b894' },
            { label: 'Model Version',    val: modelsRaw?.model_version || '—' },
            { label: 'Learning Stage',   val: 'Phase 4: Evolution',                                            color: '#a78bfa' },
          ].map(({ label, val, color }) => (
            <div key={label} className={styles.execBox}>
              <span className={styles.execLabel}>{label}</span>
              <span className={styles.execVal} style={color ? { color } : {}}>{val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* LIFECYCLE STEPPER */}
      <CycleStepper
        cycleState={cycleState}
        isCycleLoading={isCycleLoading}
        onIssueForecast={handleIssueForecast}
        onUploadActuals={(period, file) => { setCycleMonth(period); handleIngestSyntheticMonth(period, file) }}
        onReset={handleResetCycle}
        onRefetch={refetchCycle}
        isIssuingForecast={isIssuingForecast}
        isUploadingActuals={isIngestingActuals}
      />

      {/* TAB: DECISION INTELLIGENCE */}
      {activeTab === 'intelligence' && (
        <>
          <div className={styles.sectionLabel}>
            <Cpu size={14} style={{ color: 'var(--blue)' }} />
            Multi-Agent Predictions &amp; LightGBM Feature Importance
          </div>

          {cats.length === 0 ? (
            <div className={styles.emptyState}>No forecast generated &mdash; issue a forecast in the lifecycle above</div>
          ) : (
            <div className={styles.agentGrid}>
              {/* Demand */}
              <div className={styles.agentCard}>
                <div className={styles.agentHead}>
                  <div className={styles.agentName}><Users size={14} style={{ color: 'var(--blue)' }} /> Demand Agent</div>
                  <span className="badge bdg-low">{demandConf != null ? `${demandConf}%` : '—'}</span>
                </div>
                <div className={styles.agentPredVal}>{totalDemand.toLocaleString()} <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--tm)' }}>units</span></div>
                {ingestedTotal != null && (
                  <div style={{ fontSize: 10, display: 'flex', gap: 8 }}>
                    <span style={{ color: '#00b894', fontWeight: 700 }}>&#10003; Actual: {ingestedTotal.toLocaleString()}</span>
                    <span style={{ color: ingestedTotal < ingestedForecast ? '#d63031' : '#00b894', fontWeight: 700 }}>
                      {ingestedTotal < ingestedForecast ? '▼' : '▲'} {Math.abs(ingestedTotal - ingestedForecast).toLocaleString()}
                    </span>
                  </div>
                )}
                <div style={{ fontSize: 10, color: 'var(--ts)' }}>{cats.length} categories &middot; {cycleMonth}</div>
                {totalRevenue > 0 && <div style={{ fontSize: 10, color: 'var(--ts)' }}>Est. Revenue: <strong style={{ color: 'var(--blue)' }}>${totalRevenue.toLocaleString()}</strong></div>}
                <div className={styles.agentDivider} />
                <div style={{ fontSize: 10, color: 'var(--tm)', marginBottom: 2 }}>Top Features (LightGBM)</div>
                <div className={styles.featureList}>
                  {demandFeatures.map((f, i) => (
                    <div key={i}>
                      <div className={styles.featureBarRow}><span>{f.name}</span><span style={{ fontWeight: 700 }}>{f.pct}%</span></div>
                      <div className={styles.featureBarBg}><div className={styles.featureBarFill} style={{ width: `${f.pct}%`, background: 'var(--blue)' }} /></div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Supplier */}
              <div className={styles.agentCard}>
                <div className={styles.agentHead}>
                  <div className={styles.agentName}><Factory size={14} style={{ color: '#e67e22' }} /> Supplier Agent</div>
                  <span className="badge bdg-med">{demandConf != null ? `${demandConf}%` : '—'}</span>
                </div>
                <div className={styles.agentPredVal} style={{ color: '#e67e22' }}>{avgLateRisk != null ? `${(avgLateRisk*100).toFixed(1)}%` : '—'} <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--tm)' }}>late risk</span></div>
                <div style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--ts)' }}>
                  <span>High: <strong>{highRisk}</strong></span>
                  <span>Med: <strong>{medRisk}</strong></span>
                  <span>Low: <strong>{lowRisk}</strong></span>
                </div>
                <div className={styles.agentDivider} />
                <div style={{ fontSize: 10, color: 'var(--tm)', marginBottom: 2 }}>Top Features (LightGBM)</div>
                <div className={styles.featureList}>
                  {supplierFeatures.map((f, i) => (
                    <div key={i}>
                      <div className={styles.featureBarRow}><span>{f.name}</span><span style={{ fontWeight: 700 }}>{f.pct}%</span></div>
                      <div className={styles.featureBarBg}><div className={styles.featureBarFill} style={{ width: `${f.pct}%`, background: '#e67e22' }} /></div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Logistics */}
              <div className={styles.agentCard}>
                <div className={styles.agentHead}>
                  <div className={styles.agentName}><Truck size={14} style={{ color: '#d63031' }} /> Logistics Agent</div>
                  <span className="badge bdg-high">{demandConf != null ? `${demandConf}%` : '—'}</span>
                </div>
                <div className={styles.agentPredVal} style={{ color: '#d63031' }}>{avgShipDays != null ? `${avgShipDays.toFixed(2)}d` : '—'} <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--tm)' }}>avg delay</span></div>
                <div style={{ fontSize: 10, color: 'var(--ts)' }}>Highest: <strong>{[...cats].sort((a,b)=>(b.avg_shipping_days||0)-(a.avg_shipping_days||0))[0]?.category || '—'}</strong></div>
                <div className={styles.agentDivider} />
                <div style={{ fontSize: 10, color: 'var(--tm)', marginBottom: 2 }}>Top Features (LightGBM)</div>
                <div className={styles.featureList}>
                  {logisticsFeatures.map((f, i) => (
                    <div key={i}>
                      <div className={styles.featureBarRow}><span>{f.name}</span><span style={{ fontWeight: 700 }}>{f.pct}%</span></div>
                      <div className={styles.featureBarBg}><div className={styles.featureBarFill} style={{ width: `${f.pct}%`, background: '#d63031' }} /></div>
                    </div>
                  ))}
                </div>
              </div>

              {/* All categories summary */}
              <div className={styles.agentCard}>
                <div className={styles.agentHead}>
                  <div className={styles.agentName}><BarChart2 size={14} style={{ color: '#7c6fcd' }} /> All Categories</div>
                  <span className="badge" style={{ background: 'rgba(124,111,205,0.12)', color: '#7c6fcd', border: '1px solid rgba(124,111,205,0.25)', fontSize: 9 }}>{cats.length}</span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--tp)' }}>{cycleMonth} Forecast</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {cats.slice(0, 9).map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 9 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: (c.combined_risk||0) >= 0.65 ? '#d63031' : (c.combined_risk||0) >= 0.35 ? '#f59e0b' : '#00b894' }} />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--ts)' }}>{c.category}</span>
                      <span style={{ color: 'var(--tm)', flexShrink: 0 }}>{c.region?.slice(0,6)}</span>
                      <span style={{ fontWeight: 700, color: 'var(--blue)', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{c.predicted_demand != null ? c.predicted_demand.toLocaleString() : '—'}</span>
                    </div>
                  ))}
                  {cats.length > 9 && <div style={{ fontSize: 9, color: 'var(--tm)', textAlign: 'center' }}>+{cats.length - 9} more &darr;</div>}
                </div>
              </div>
            </div>
          )}

          {/* Coordination flow */}
          <div className={styles.coordinationCard}>
            <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--tp)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <GitBranch size={14} style={{ color: 'var(--blue)' }} /> Live Multi-Agent Coordination Flow
            </div>
            <div className={styles.flowContainer}>
              {[
                { icon: <Users size={15} style={{ color: 'var(--blue)' }} />,    label: 'Demand Agent',    sub: totalDemand > 0 ? `${totalDemand.toLocaleString()} units` : '—' },
                { arrow: true },
                { icon: <Factory size={15} style={{ color: '#e67e22' }} />,      label: 'Supplier Agent',  sub: avgLateRisk != null ? `${(avgLateRisk*100).toFixed(1)}% risk` : '—' },
                { arrow: true },
                { icon: <Warehouse size={15} style={{ color: '#d4a017' }} />,    label: 'Inventory',       sub: 'Buffer OK' },
                { arrow: true },
                { icon: <Truck size={15} style={{ color: '#d63031' }} />,        label: 'Logistics Agent', sub: avgShipDays != null ? `${avgShipDays.toFixed(2)}d delay` : '—' },
                { arrow: true },
                { icon: <Rocket size={15} style={{ color: 'var(--blue)' }} />,   label: 'Decision Coord.', sub: overallConf != null ? `${(overallConf*100).toFixed(1)}% conf` : '—', highlight: true },
              ].map((n, i) => n.arrow
                ? <span key={i} className={styles.flowArrow}>&rarr;</span>
                : (
                  <div key={i} className={styles.flowNode} style={n.highlight ? { borderColor: 'var(--blue)', background: 'rgba(59,130,246,0.08)' } : {}}>
                    {n.icon}
                    <span style={{ fontSize: 10, fontWeight: 800, color: n.highlight ? 'var(--blue)' : 'var(--tp)' }}>{n.label}</span>
                    <span style={{ fontSize: 9, color: n.highlight ? '#00b894' : 'var(--tm)', fontWeight: n.highlight ? 700 : 400 }}>{n.sub}</span>
                  </div>
                )
              )}
            </div>
          </div>

          {/* Charts */}
          <div className={styles.sectionLabel}><BarChart2 size={14} style={{ color: 'var(--blue)' }} /> Forecast Charts</div>

          {/* Demand bar chart */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <BarChart2 size={13} style={{ color: 'var(--blue)' }} />
                Predicted Demand by Category &middot; {cycleMonth} &middot; {filteredCategoryForecasts.length}/{cats.length}
              </span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <div className={styles.filterInput} style={{ flex: '0 1 160px' }}>
                  <Search size={10} color="var(--tm)" />
                  <input value={catSearch} onChange={e => setCatSearch(e.target.value)} placeholder="Search..." />
                  {catSearch && <button onClick={() => setCatSearch('')} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--tm)', fontSize: 12, padding: 0 }}>&times;</button>}
                </div>
                <select className={styles.filterSelect} value={catRegionFilter} onChange={e => setCatRegionFilter(e.target.value)}>
                  {allRegions.map(r => <option key={r} value={r}>{r === 'All' ? 'All Regions' : r}</option>)}
                </select>
                <select className={styles.filterSelect} value={catRiskFilter} onChange={e => setCatRiskFilter(e.target.value)}>
                  <option value="All">All Risk</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
                {(catSearch || catRegionFilter !== 'All' || catRiskFilter !== 'All') && (
                  <button onClick={() => { setCatSearch(''); setCatRegionFilter('All'); setCatRiskFilter('All') }} className={styles.filterSelect} style={{ cursor: 'pointer' }}>Clear</button>
                )}
              </div>
            </div>
            {(() => {
              const actualsMap = {}
              if (cycleActualsUploaded && cycleUploadResult?.comparison_records) {
                cycleUploadResult.comparison_records.forEach(r => { if (r.actual_value != null) actualsMap[r.entity_id] = r.actual_value })
              }
              const chartData = filteredCategoryForecasts.map(c => ({
                name: `${c.category} (${c.region?.slice(0,5)})`,
                demand: c.predicted_demand,
                actual: actualsMap[`${c.category} (${c.region})`] != null ? Math.round(actualsMap[`${c.category} (${c.region})`]) : null,
                _risk: c.combined_risk || 0,
              }))
              const hasActuals = Object.keys(actualsMap).length > 0
              if (filteredCategoryForecasts.length === 0) return <div className={styles.emptyState}>No categories match filters</div>
              return (
                <div style={{ height: Math.max(220, filteredCategoryForecasts.length * 22) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 4, right: 40, top: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                      <YAxis dataKey="name" type="category" tick={{ fontSize: 8, fill: 'var(--tm)' }} width={155} axisLine={false} tickLine={false} />
                      <Tooltip content={<ChartTip />} />
                      {hasActuals && <Legend wrapperStyle={{ fontSize: 9 }} />}
                      <Bar dataKey="demand" name="Predicted" radius={[0,3,3,0]} barSize={hasActuals ? 7 : 13}>
                        {chartData.map((c, i) => <Cell key={i} fill={c._risk >= 0.65 ? '#d63031' : c._risk >= 0.35 ? '#f59e0b' : 'var(--blue)'} />)}
                      </Bar>
                      {hasActuals && <Bar dataKey="actual" name="Actual" radius={[0,3,3,0]} barSize={7} fill="#00b894" />}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )
            })()}
          </div>

          {/* Risk pie + Confidence line */}
          <div className={styles.chartsRow}>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertTriangle size={13} style={{ color: '#e67e22' }} /> Risk Distribution &middot; {cats.length} categories
              </div>
              <div style={{ height: 200, display: 'flex', alignItems: 'center' }}>
                {cats.length === 0 ? <div className={styles.emptyState}>No forecast yet</div> : (() => {
                  const pieData = [
                    { name: `High (${highRisk})`, value: highRisk, color: '#d63031' },
                    { name: `Med (${medRisk})`,   value: medRisk,  color: '#f59e0b' },
                    { name: `Low (${lowRisk})`,   value: lowRisk,  color: '#00b894' },
                  ].filter(d => d.value > 0)
                  return (
                    <>
                      <div style={{ width: '55%', height: '100%' }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={4} dataKey="value">
                              {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                            </Pie>
                            <Tooltip formatter={(v, n) => [v + ' categories', n]} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div style={{ width: '45%', display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 8 }}>
                        {pieData.map((d, i) => (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                            <span style={{ fontSize: 10.5, color: 'var(--tp)', fontWeight: 600 }}>{d.name}</span>
                          </div>
                        ))}
                        <div style={{ fontSize: 9.5, color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: 6, marginTop: 4 }}>
                          Total: <strong>{cats.length}</strong> category&times;region pairs
                        </div>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>

            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={13} style={{ color: '#00b894' }} /> Prediction Confidence Timeline
              </div>
              <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={confidenceTimeline} margin={{ left: -15, right: 10, top: 8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} domain={[70, 100]} unit="%" />
                    <Tooltip content={<ChartTip />} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    <Line type="monotone" dataKey="prediction_confidence" name="Prediction %" stroke="var(--blue)" strokeWidth={2} dot={false} connectNulls={false} />
                    <Line type="monotone" dataKey="validation_confidence" name="Validation %" stroke="#00b894" strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls={false} />
                    <Line type="monotone" dataKey="rolling_average" name="Rolling Avg" stroke="#a78bfa" strokeWidth={1.5} dot={false} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Historical vs Forecast timeline */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={13} style={{ color: 'var(--blue)' }} /> Historical Orders vs Model Predictions &middot; {cycleMonth}
            </div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={historicalForecastSeries} margin={{ left: -15, right: 10, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                  <XAxis dataKey="period" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTip />} />
                  <Legend wrapperStyle={{ fontSize: 9 }} />
                  <Bar dataKey="historical" name="Historical Orders" fill="var(--blue)" barSize={14} radius={[3,3,0,0]} />
                  <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#00b894" strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} />
                  <Line type="monotone" dataKey="actual" name="Actuals" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* TAB: VALIDATION & DIAGNOSTICS */}
      {activeTab === 'validation' && (
        <ValidationPanel
          cycleMonth={cycleMonth}
          cycleStep={cycleStep}
          cycleActualsUploaded={cycleActualsUploaded}
          actualsFile={actualsFile}
          setActualsFile={setActualsFile}
          isIngestingActuals={isIngestingActuals}
          cycleUploadResult={cycleUploadResult}
          handleIngestSyntheticMonth={handleIngestSyntheticMonth}
          setValidationResult={() => {}}
          setCycleUploadResult={setCycleUploadResult}
          errorDiagnostics={filteredDiagnostics}
          historicalForecastSeries={historicalForecastSeries}
          confidenceTimeline={confidenceTimeline}
          deviationData={deviationData}
          agentAccuracyData={agentAccuracyData}
          uploadHistory={uploadHistory}
          activeCycleId={null}
          cycleStages={[]}
          cycleComplete={false}
          wsConnected={false}
        />
      )}

    </div>
  )
}
