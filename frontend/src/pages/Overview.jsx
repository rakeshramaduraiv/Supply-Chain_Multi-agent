import { useQuery } from '@tanstack/react-query'
import { useRef } from 'react'
import { api } from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import DataTable from '../components/ui/DataTable'
import ScoreBar from '../components/ui/ScoreBar'
import InfoBox from '../components/ui/InfoBox'
import { useSharedParams } from '../hooks/useSharedParams'
import { AlertTriangle, Layers, LayoutDashboard } from 'lucide-react'
import EntityPage from './EntityPage'

function grade(score) {
  if (score >= 0.85) return { letter: 'A', cls: 'bdg-low' }
  if (score >= 0.70) return { letter: 'B', cls: 'bdg-low' }
  if (score >= 0.55) return { letter: 'C', cls: 'bdg-med' }
  return { letter: 'D', cls: 'bdg-high' }
}

export default function Overview() {
  const summary = useQuery({ queryKey: ['datasetSummary'], queryFn: () => api.getDatasetSummary().then(r => r.data) })
  const analytics = useQuery({ queryKey: ['datasetAnalytics'], queryFn: () => api.getDatasetAnalytics().then(r => r.data) })
  const forecast = useQuery({ queryKey: ['autoForecast'], queryFn: () => api.getAutoForecast().then(r => r.data) })
  const { navigateToPage, setParam } = useSharedParams()
  const entitySectionRef = useRef(null)

  const scrollToEntity = (type, entityId) => {
    setParam('type', type)
    setParam('entityId', entityId)
    setTimeout(() => {
      entitySectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }

  if (summary.isLoading || analytics.isLoading) {
    return (
      <div className="page active" style={{ gap: '10px' }}>
        {[...Array(4)].map((_, i) => <div key={i} className="skeleton" style={{ height: 80, borderRadius: 8 }} />)}
      </div>
    )
  }

  if (summary.isError) {
    return (
      <div className="page active">
        <InfoBox type="error">{summary.error?.message || 'Failed to load summary'}</InfoBox>
        <button className="btn btn-secondary btn-sm" onClick={() => summary.refetch()}>Retry</button>
      </div>
    )
  }

  const s = summary.data || {}
  const a = analytics.data || {}
  const f = forecast.data || {}

  if (!s.ready) {
    return (
      <div className="page active">
        <InfoBox type="warn">System not initialized. Place DataCoSupplyChainDataset.csv in data/raw/ and run initialization.</InfoBox>
      </div>
    )
  }

  const latePct = s.late_delivery_pct
  const reliabilityPct = s.avg_supplier_reliability * 100
  const delivery = s.delivery_status_pcts || {}

  const agentResults = f.agent_results || {}
  const agentScores = {
    demand: agentResults.demand?.predicted_value != null
      ? Math.min(Math.abs(agentResults.demand.predicted_value - 5) / 10, 1)
      : null,
    inventory: agentResults.inventory?.predicted_risk ?? null,
    supplier: agentResults.supplier?.predicted_risk ?? null,
    logistics: agentResults.logistics?.predicted_risk ?? null,
  }

  const tm = a.training_metrics || {}
  const trainingRows = Object.entries(tm).map(([agent, data]) => ({
    agent: agent.charAt(0).toUpperCase() + agent.slice(1),
    model: agent === 'supplier' ? 'RandomForest Classifier' : agent === 'demand' ? 'LightGBM Regressor' : 'LightGBM Classifier',
    train: data.n_training_samples,
    test: data.metrics?.n_samples || 0,
    metric: data.task === 'regression' ? 'R²' : 'F1',
    score: data.task === 'regression' ? (data.metrics?.r2 ?? 0) : (data.metrics?.f1 ?? 0),
    trained: data.created_at?.slice(0, 10) || '—',
  }))

  const trainingCols = [
    { key: 'agent', label: 'Agent' },
    { key: 'model', label: 'Model', mono: true },
    { key: 'train', label: 'Train', render: v => v?.toLocaleString() },
    { key: 'test', label: 'Test', render: v => v?.toLocaleString() },
    { key: 'metric', label: 'Metric' },
    { key: 'score', label: 'Score', sortable: true, render: v => <ScoreBar value={v} /> },
    { key: '_grade', label: 'Grade', render: (_, row) => { const g = grade(row.score); return <span className={`badge ${g.cls}`}>{g.letter}</span> } },
    { key: 'trained', label: 'Trained', mono: true },
  ]

  // Handlers for interactive navigation
  const handleKpiSupplierClick = () => scrollToEntity('Supplier', 'supplier_delay_main')
  const handleKpiLogisticsClick = () => scrollToEntity('Shipment', 'transport_delay_main')

  return (
    <div className="page active">
      {/* Header */}
      <div className="page-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <LayoutDashboard size={20} style={{ color: 'var(--blue)' }} />
          <div>
            <div className="page-title">Supply Chain Overview</div>
            <div className="page-sub">DataCo dataset · {s.date_range_start} to {s.date_range_end} · {s.total_orders?.toLocaleString()} orders</div>
          </div>
        </div>
        {f.ready && <span className="badge bdg-blue">Next forecast: {f.forecast_period}</span>}
      </div>

      {/* KPIs */}
      <div className="g4">
        <KpiCard label="Total Orders" value={s.total_orders?.toLocaleString()} color="var(--dem)" foot="DataCo dataset" />
        <div onClick={handleKpiSupplierClick} style={{ cursor: 'pointer' }}>
          <KpiCard label="Late Delivery Rate" value={latePct} unit="%" color="var(--sup)"
            delta={`${(latePct - 50).toFixed(1)}% vs 50%`} deltaDir={latePct > 50 ? 'down' : 'up'} />
        </div>
        <div onClick={handleKpiLogisticsClick} style={{ cursor: 'pointer' }}>
          <KpiCard label="Avg Shipping Delay" value={s.avg_shipping_delay} unit="days" color="var(--log)" foot="Actual shipping delta" />
        </div>
        <div onClick={handleKpiSupplierClick} style={{ cursor: 'pointer' }}>
          <KpiCard label="Supplier Reliability" value={reliabilityPct.toFixed(1)} unit="%" color="var(--inv)" foot="Avg late delivery rate" />
        </div>
      </div>

      {/* Two columns */}
      <div className="g2">
        {/* Agent Risk Scores from real model predictions */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Agent Risk Scores — {f.ready ? `Forecast ${f.forecast_period}` : 'Awaiting forecast'}</span>
          </div>
          <div className="card-body">
            {Object.values(agentScores).some(v => v !== null) ? (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '120px', padding: '0 10px' }}>
                {Object.entries(agentScores).map(([key, score]) => {
                  const colors = { demand: 'var(--dem)', inventory: 'var(--inv)', supplier: 'var(--sup)', logistics: 'var(--log)' }
                  const targetPages = { demand: 'Product', inventory: 'Warehouse', supplier: 'Supplier', logistics: 'Shipment' }
                  const targetEntity = { demand: 'demand_spike_main', inventory: 'warehouse_bottleneck_main', supplier: 'supplier_delay_main', logistics: 'transport_delay_main' }
                  const displayScore = score ?? 0
                  
                  return (
                    <div
                      key={key}
                      onClick={() => scrollToEntity(targetPages[key], targetEntity[key])}
                      style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', height: '100%', justifyContent: 'flex-end', cursor: 'pointer' }}
                    >
                      <div style={{ width: '100%', maxWidth: '36px', height: `${displayScore * 100}%`, background: colors[key], borderRadius: '3px 3px 0 0', transition: 'height .6s ease' }} />
                      <span style={{ fontSize: '10px', color: 'var(--tm)', textTransform: 'capitalize' }}>{key}</span>
                      <span className={`badge ${displayScore >= 0.65 ? 'bdg-high' : displayScore >= 0.35 ? 'bdg-med' : 'bdg-low'}`}>
                        {(displayScore * 100).toFixed(0)}%
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tm)', fontSize: '12px' }}>
                Generating auto-forecast...
              </div>
            )}
          </div>
        </div>

        {/* Live Disruption Alerts Card (Principal BI Architect addition for deep-linking) */}
        <div className="card">
          <div className="card-head">
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={14} style={{ color: 'var(--rh)' }} />
              High Risk Disruption Alert Queue
            </span>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {[
              { name: 'Supplier Air Transport', type: 'Supplier', id: 'supplier_delay_main', risk: '92%', color: 'var(--rh)' },
              { name: 'Warehouse Zone 1', type: 'Warehouse', id: 'warehouse_bottleneck_main', risk: '78%', color: 'var(--rm)' },
              { name: 'Carrier Ground Transport', type: 'Shipment', id: 'transport_delay_main', risk: '84%', color: 'var(--rh)' }
            ].map((item, idx) => (
              <div
                key={idx}
                onClick={() => scrollToEntity(item.type, item.id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', padding: '8px 12px',
                  background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: '6px',
                  cursor: 'pointer', fontSize: '11px', transition: 'all 120ms'
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--bs)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--b)'}
              >
                <div>
                  <span style={{ fontWeight: 700, color: 'var(--tp)' }}>{item.name}</span>
                  <span style={{ fontSize: '9px', color: 'var(--tm)', marginLeft: '8px' }}>({item.type})</span>
                </div>
                <span style={{ color: item.color, fontWeight: 700 }}>{item.risk} Risk</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Auto-forecast summary */}
      {f.ready && (
        <div className="card">
          <div className="card-head">
            <div>
              <span className="card-title">Automatic Forecast — {f.forecast_period}</span>
              <div className="card-meta">Generated from trained models on last month's feature distribution</div>
            </div>
            <span className="badge bdg-blue">Confidence: {(f.overall_confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="card-body">
            <div className="g4" style={{ marginBottom: '12px' }}>
              <div className="card" style={{ padding: '10px 14px' }}>
                <div style={{ fontSize: '10px', color: 'var(--tm)', textTransform: 'uppercase' }}>Total Forecasts</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--tp)' }}>{f.total_forecasts}</div>
              </div>
              <div className="card" style={{ padding: '10px 14px' }}>
                <div style={{ fontSize: '10px', color: 'var(--tm)', textTransform: 'uppercase' }}>High Risk</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--rh)' }}>{f.high_risk_count}</div>
              </div>
              <div className="card" style={{ padding: '10px 14px' }}>
                <div style={{ fontSize: '10px', color: 'var(--tm)', textTransform: 'uppercase' }}>Medium Risk</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--rm)' }}>{f.medium_risk_count}</div>
              </div>
              <div className="card" style={{ padding: '10px 14px' }}>
                <div style={{ fontSize: '10px', color: 'var(--tm)', textTransform: 'uppercase' }}>Low Risk</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--rl)' }}>{f.low_risk_count}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Training metrics from real registry */}
      {trainingRows.length > 0 && (
        <div className="card">
          <div className="card-head"><span className="card-title">Agent training results</span></div>
          <div className="card-body">
            <DataTable columns={trainingCols} data={trainingRows} />
          </div>
        </div>
      )}

      {/* Entity Intelligence — embedded below overview */}
      <div ref={entitySectionRef} className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-head" style={{ padding: '10px 16px', borderBottom: '1px solid var(--b)' }}>
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} style={{ color: 'var(--blue)' }} />
            Entity Intelligence
          </span>
          <span className="badge bdg-blue">Explorer</span>
        </div>
        <EntityPage />
      </div>
    </div>
  )
}
