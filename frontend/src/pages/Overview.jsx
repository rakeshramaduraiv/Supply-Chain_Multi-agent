import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import InfoBox from '../components/ui/InfoBox'
import Spinner from '../components/ui/Spinner'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { LayoutDashboard, AlertTriangle } from 'lucide-react'

const AGENTS = [
  {
    key: 'demand',
    label: 'Demand Agent',
    color: 'var(--dem)',
    purpose: 'Predict customer demand across products and geographies.',
    businessRole: 'Demand planning and inventory allocation.',
    modelDefault: 'LightGBM Regressor',
    targetVariable: 'Demand volume',
    entities: ['Customer', 'Product', 'Order'],
  },
  {
    key: 'inventory',
    label: 'Inventory Agent',
    color: 'var(--inv)',
    purpose: 'Detect inventory risk and stock imbalance across warehouses.',
    businessRole: 'Inventory optimization and buffer planning.',
    modelDefault: 'LightGBM Classifier',
    targetVariable: 'Stock risk',
    entities: ['Warehouse', 'Product', 'Shipment'],
  },
  {
    key: 'supplier',
    label: 'Supplier Agent',
    color: 'var(--sup)',
    purpose: 'Model supplier delivery reliability and disruption risk.',
    businessRole: 'Supplier performance and contract risk.',
    modelDefault: 'LightGBM Classifier',
    targetVariable: 'Supplier risk',
    entities: ['Supplier', 'Warehouse', 'Shipment'],
  },
  {
    key: 'logistics',
    label: 'Logistics Agent',
    color: 'var(--log)',
    purpose: 'Monitor transit and delivery performance for shipments.',
    businessRole: 'Logistics route and carrier risk.',
    modelDefault: 'LightGBM Classifier',
    targetVariable: 'Delivery risk',
    entities: ['Shipment', 'Warehouse', 'Region'],
  },
]

const ENTITY_TYPES = ['Customer', 'Order', 'Product', 'Supplier', 'Warehouse', 'Shipment', 'Calendar Event']

const entityAgentMap = {
  Customer: 'Demand Agent',
  Order: 'Demand Agent',
  Product: 'Demand Agent',
  Supplier: 'Supplier Agent',
  Warehouse: 'Inventory Agent',
  Shipment: 'Logistics Agent',
  'Calendar Event': 'Logistics Agent',
}

export default function Overview() {
  const [selectedAgent, setSelectedAgent] = useState('demand')
  const [selectedEntity, setSelectedEntity] = useState('Product')

  const dashboardQuery = useQuery({ queryKey: ['businessDashboard'], queryFn: () => api.getBusinessDashboard().then(r => r.data), refetchInterval: 60000, retry: false })
  const forecastQuery = useQuery({ queryKey: ['businessForecast'], queryFn: () => api.getBusinessForecast().then(r => r.data), refetchInterval: 60000, retry: false })
  const graphQuery = useQuery({ queryKey: ['businessGraph'], queryFn: () => api.getBusinessGraph().then(r => r.data), refetchInterval: 60000, retry: false })
  const systemQuery = useQuery({ queryKey: ['businessSystem'], queryFn: () => api.getBusinessSystem().then(r => r.data), refetchInterval: 60000, retry: false })
  const analyticsQuery = useQuery({ queryKey: ['datasetAnalytics'], queryFn: () => api.getDatasetAnalytics().then(r => r.data), refetchInterval: 120000, retry: false })
  const summaryQuery = useQuery({ queryKey: ['datasetSummary'], queryFn: () => api.getDatasetSummary().then(r => r.data), refetchInterval: 120000, retry: false })
  const intelQuery = useQuery({ queryKey: ['businessIntel'], queryFn: () => api.getBusinessIntel().then(r => r.data), refetchInterval: 60000, retry: false })
  const trainingHistoryQuery = useQuery({ queryKey: ['trainingHistory'], queryFn: () => api.getTrainingHistory().then(r => r.data), refetchInterval: 120000, retry: false })
  const featureImportanceQuery = useQuery({ queryKey: ['featureImportance', selectedAgent], queryFn: () => api.getFeatureImportance(selectedAgent).then(r => r.data), enabled: !!selectedAgent, retry: false })

  const loading = [dashboardQuery, forecastQuery, graphQuery, systemQuery, analyticsQuery, summaryQuery].some(q => q.isLoading)
  const error = [dashboardQuery, forecastQuery, graphQuery, systemQuery, analyticsQuery, summaryQuery].find(q => q.isError)

  if (loading) {
    return <Spinner large text="Loading dashboard insights from backend APIs..." />
  }

  if (error) {
    return (
      <div className="page active">
        <InfoBox type="error">{error.error?.message || 'Unable to load dashboard data from backend APIs.'}</InfoBox>
      </div>
    )
  }

  const dashboard = dashboardQuery.data || {}
  const forecast = forecastQuery.data || {}
  const graph = graphQuery.data || {}
  const system = systemQuery.data || {}
  const analytics = analyticsQuery.data || {}
  const summary = summaryQuery.data || {}
  const intelligence = intelQuery.data || {}
  const featureImportanceData = featureImportanceQuery.data || {}

  const selectedAgentInfo = AGENTS.find(agent => agent.key === selectedAgent) || AGENTS[0]
  const selectedAgentMetrics = analytics.training_metrics?.[selectedAgent] || {}
  const selectedAgentDetails = {
    modelUsed: selectedAgentMetrics.task ? (selectedAgentMetrics.task === 'regression' ? 'LightGBM Regressor' : 'LightGBM Classifier') : selectedAgentInfo.modelDefault,
    targetVariable: selectedAgentInfo.targetVariable,
    predictionOutput: selectedAgentInfo.key === 'demand' ? 'Demand forecast' : 'Risk prediction',
  }
  const agentEntities = selectedAgentInfo.entities

  const entityCounts = {
    Customer: graph.entity_breakdown?.Customer ?? 0,
    Order: graph.entity_breakdown?.Order ?? 0,
    Product: graph.entity_breakdown?.Product ?? 0,
    Supplier: graph.entity_breakdown?.Supplier ?? 0,
    Warehouse: graph.entity_breakdown?.Warehouse ?? 0,
    Shipment: graph.entity_breakdown?.Shipment ?? 0,
    'Calendar Event': graph.entity_breakdown?.Event ?? graph.entity_breakdown?.CalendarEvent ?? 0,
  }

  const entityHealth = {
    Customer: graph.graph_health || 'Healthy',
    Order: graph.graph_health || 'Healthy',
    Product: graph.graph_health || 'Healthy',
    Supplier: graph.graph_health || 'Healthy',
    Warehouse: graph.graph_health || 'Healthy',
    Shipment: graph.graph_health || 'Healthy',
    'Calendar Event': graph.graph_health || 'Healthy',
  }

  const recentActivities = useMemo(() => {
    const activity = []
    if (dashboard.last_updated) {
      activity.push({ label: 'Last updated', value: new Date(dashboard.last_updated).toLocaleString() })
    }
    if (dashboard.recent_activity?.length) {
      dashboard.recent_activity.slice(0, 3).forEach((item, index) => activity.push({ label: `Activity ${index + 1}`, value: typeof item === 'string' ? item : item.message || JSON.stringify(item) }))
    }
    if (dashboard.alerts?.length) {
      dashboard.alerts.slice(0, 2).forEach((alert, index) => activity.push({ label: `Alert ${index + 1}`, value: alert.name || alert.message || 'Policy update' }))
    }
    return activity
  }, [dashboard])

  const trainingHistory = trainingHistoryQuery.data || { entries: [] }
  const accuracyTrendData = useMemo(() => {
    const entries = trainingHistory.entries || []
    const dates = Array.from(new Set(entries.map(entry => entry.created_at?.slice(0, 10) || ''))).filter(Boolean).sort()
    return dates.map(period => {
      const row = { period }
      AGENTS.forEach(agent => {
        const entry = entries.find(item => item.intelligence_type === agent.key && item.created_at?.slice(0, 10) === period)
        row[agent.key] = entry?.metrics?.accuracy ?? entry?.metrics?.f1 ?? entry?.metrics?.r2 ?? null
      })
      return row
    })
  }, [trainingHistory])

  const chartLines = AGENTS.map(agent => ({ key: agent.key, stroke: agent.color, name: agent.label }))

  const selectedAgentForecasts = useMemo(() => {
    const typeMap = { demand: 'Product', inventory: 'Warehouse', supplier: 'Supplier', logistics: 'Shipment' }
    return (forecast.forecasts || []).filter(item => item.entity_type === typeMap[selectedAgent]).slice(0, 4)
  }, [forecast.forecasts, selectedAgent])

  const graphRagSummary = {
    totalQueries: intelligence.total_insights ?? 0,
    avgResponseTime: intelligence.avg_response_ms ? `${intelligence.avg_response_ms} ms` : 'N/A',
    recentQuery: intelligence.insights?.[0]?.title || dashboard.alerts?.[0]?.message || 'No recent GraphRAG query',
  }

  const timelineCurrentStage = system.initialized ? 'Decision Dashboard' : 'Feature Engineering'
  const TIMELINE_STEPS = [
    { id: 'dataset', label: 'Historical Dataset', status: 'done', index: 1 },
    { id: 'feature', label: 'Data Cleaning', status: 'done', index: 2 },
    { id: 'multiAgent', label: 'Feature Engineering', status: 'done', index: 3 },
    { id: 'knowledgeGraph', label: 'Multi-Agent AI', status: 'done', index: 4 },
    { id: 'graphRAG', label: 'Knowledge Graph', status: 'done', index: 5 },
    { id: 'rootCause', label: 'GraphRAG', status: 'done', index: 6 },
    { id: 'decision', label: 'Root Cause Analysis', status: system.initialized ? 'done' : 'active', index: 7 },
    { id: 'learning', label: 'Decision Dashboard', status: system.initialized ? 'active' : 'done', index: 8 },
  ]

  return (
    <div className="page active">
      <div className="page-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <LayoutDashboard size={20} style={{ color: 'var(--blue)' }} />
          <div>
            <div className="page-title">AMASCI Dashboard</div>
            <div className="page-sub">Executive overview of dataset readiness, model health, knowledge graph state, and AI operations.</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="badge bdg-blue">Forecast: {forecast.forecast_period || 'Pending'}</span>
          <span className="badge bdg-purple">Last updated: {dashboard.last_updated ? new Date(dashboard.last_updated).toLocaleString() : 'Loading'}</span>
          <span className="badge bdg-low">Health: {dashboard.health_status || 'N/A'}</span>
          <span className="badge bdg-orange">Training: {system.initialized ? 'Complete' : 'Pending'}</span>
        </div>
      </div>

      <div className="g4">
        <KpiCard label="Historical Records" value={summary.total_orders?.toLocaleString() ?? 0} foot={`${summary.date_range_start} → ${summary.date_range_end}`} color="var(--blue)" />
        <KpiCard label="Knowledge Graph" value={`${(graph.total_entities ?? 0).toLocaleString()} nodes`} foot={`${(graph.total_connections ?? 0).toLocaleString()} relationships`} color="var(--sup)" />
        <KpiCard label="Machine Learning" value={`${AGENTS.length} intelligent agents`} foot={`Training ${system.initialized ? 'complete' : 'in progress'}`} color="var(--inv)" />
        <KpiCard label="Forecast Summary" value={forecast.forecast_period || 'Pending'} foot={`${forecast.high_risk_count ?? 0} high risk · ${forecast.total_predictions ?? 0} forecasts`} color="var(--dem)" />
      </div>

      <div className="g4">
        <KpiCard label="GraphRAG" value={graphRagSummary.totalQueries} foot={`Recent: ${graphRagSummary.recentQuery}`} color="var(--tpke)" />
        <KpiCard label="System Health" value={system.system_status || 'Operational'} foot="FastAPI · Neo4j · PostgreSQL · LightGBM · GraphRAG · TPKE" color="var(--blue)" />
      </div>

      <div className="g2">
        <div className="card">
          <div className="card-head"><span className="card-title">Monthly Sales Trend</span></div>
          <div className="card-body" style={{ minHeight: 250 }}>
            {(analytics.monthly_trend?.length ?? 0) > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={analytics.monthly_trend.slice(-12)} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="total_sales" stroke="var(--blue)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: 'var(--tm)', padding: '20px', textAlign: 'center' }}>Historical sales trend is not available yet.</div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Forecast Accuracy Trend</span></div>
          <div className="card-body" style={{ minHeight: 250 }}>
            {accuracyTrendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={accuracyTrendData} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={value => (value != null ? `${Number(value).toFixed(1)}%` : '—')} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {chartLines.map(line => (
                    <Line key={line.key} type="monotone" dataKey={line.key} name={line.name} stroke={line.stroke} strokeWidth={1.5} dot={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: 'var(--tm)', padding: '20px', textAlign: 'center' }}>Detailed agent accuracy history is not available yet.</div>
            )}
          </div>
        </div>
      </div>

      <div className="g21">
        <div>
          <div className="card">
            <div className="card-head"><span className="card-title">Multi-Agent Intelligence Panel</span></div>
            <div className="card-body" style={{ display: 'grid', gap: 16 }}>
              <div className="g4">
                {AGENTS.map(agent => {
                  const metrics = analytics.training_metrics?.[agent.key] || {}
                  const score = metrics.metrics?.accuracy ?? metrics.metrics?.f1 ?? metrics.metrics?.r2 ?? 0
                  return (
                    <button key={agent.key} type="button" onClick={() => setSelectedAgent(agent.key)} className="agent-card" style={{ borderColor: selectedAgent === agent.key ? 'var(--blue)' : undefined, cursor: 'pointer' }}>
                      <div className="agent-accent" style={{ background: agent.color }} />
                      <div className="agent-body">
                        <div className="agent-head">
                          <div>
                            <div className="agent-name">{agent.label}</div>
                            <div className="agent-model">{metrics.task ? (metrics.task === 'regression' ? 'LightGBM Regressor' : 'LightGBM Classifier') : agent.modelDefault}</div>
                          </div>
                          <span className={score >= 0.75 ? 'badge bdg-low' : score >= 0.55 ? 'badge bdg-med' : 'badge bdg-high'}>{score ? `${(score * 100).toFixed(0)}%` : 'Pending'}</span>
                        </div>
                        <div className="agent-metrics">
                          <div><div className="agent-metric-lbl">Status</div><div className="agent-metric-val">{metrics ? 'Operational' : 'Loading'}</div></div>
                          <div><div className="agent-metric-lbl">Last Training</div><div className="agent-metric-val">{metrics.created_at?.slice(0, 10) || '—'}</div></div>
                          <div><div className="agent-metric-lbl">Training rows</div><div className="agent-metric-val">{metrics.n_training_samples?.toLocaleString() ?? '—'}</div></div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              <div className="card">
                <div className="card-head"><span className="card-title">AI Information Drawer</span></div>
                <div className="card-body" style={{ display: 'grid', gap: 16 }}>
                  <div style={{ display: 'grid', gap: 10 }}>
                    <div className="section-lbl">Agent Overview</div>
                    <div style={{ display: 'grid', gap: 6 }}>
                      <div style={{ fontWeight: 600, color: 'var(--tp)' }}>{selectedAgentInfo.label}</div>
                      <div style={{ color: 'var(--tm)', fontSize: 13 }}>{selectedAgentInfo.purpose}</div>
                      <div style={{ color: 'var(--tm)', fontSize: 13 }}>Business role: {selectedAgentInfo.businessRole}</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 12, gridTemplateColumns: '1fr 1fr' }}>
                    <div>
                      <div className="agent-metric-lbl">Model Used</div>
                      <div className="agent-metric-val">{selectedAgentDetails.modelUsed}</div>
                    </div>
                    <div>
                      <div className="agent-metric-lbl">Target Variable</div>
                      <div className="agent-metric-val">{selectedAgentDetails.targetVariable}</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 12, gridTemplateColumns: '1fr 1fr' }}>
                    <div>
                      <div className="agent-metric-lbl">Current Performance</div>
                      <div className="agent-metric-val">{dashboard.health_status || 'Healthy'}</div>
                    </div>
                    <div>
                      <div className="agent-metric-lbl">Training Dataset</div>
                      <div className="agent-metric-val">{summary.date_range_start} → {summary.date_range_end}</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 12 }}>
                    <div className="agent-metric-lbl">Selected Features</div>
                    <div style={{ color: 'var(--tp)' }}>{selectedAgentMetrics.features_used?.slice(0, 6).join(', ') || 'Backend feature set from historical dataset'}</div>
                  </div>

                  <div style={{ display: 'grid', gap: 12, gridTemplateColumns: '1fr 1fr' }}>
                    <div>
                      <div className="agent-metric-lbl">Prediction Output</div>
                      <div className="agent-metric-val">{selectedAgentDetails.predictionOutput}</div>
                    </div>
                    <div>
                      <div className="agent-metric-lbl">Connected Knowledge Graph Entities</div>
                      <div className="agent-metric-val">{agentEntities.join(', ')}</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 10 }}>
                    <div className="agent-metric-lbl">Relationship tree</div>
                    <div style={{ color: 'var(--tm)', fontSize: 13 }}>{selectedAgentInfo.label} → {agentEntities.join(' → ')} → Prediction output</div>
                  </div>

                  <div>
                    <div className="agent-metric-lbl">Feature importance</div>
                    {featureImportanceQuery.isLoading ? (
                      <div className="skeleton" style={{ height: 90, borderRadius: 10 }} />
                    ) : featureImportanceData.feature_names?.length ? (
                      <div style={{ display: 'grid', gap: 8 }}>
                        {featureImportanceData.feature_names.slice(0, 4).map((feature, idx) => (
                          <div key={feature} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, alignItems: 'center' }}>
                            <div style={{ height: 6, borderRadius: 999, background: 'var(--s3)', overflow: 'hidden' }}>
                              <div style={{ width: `${Math.min(100, Math.round((featureImportanceData.gain_importance[idx] ?? 0) * 100))}%`, height: '100%', background: 'var(--blue)' }} />
                            </div>
                            <span style={{ fontSize: 11, color: 'var(--tm)' }}>{((featureImportanceData.gain_importance[idx] ?? 0) * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ color: 'var(--tm)', fontSize: 12 }}>Feature importance data is not available yet.</div>
                    )}
                  </div>

                  <div>
                    <div className="agent-metric-lbl">Recent prediction history</div>
                    <div style={{ display: 'grid', gap: 10 }}>
                      {selectedAgentForecasts.length > 0 ? selectedAgentForecasts.map((item, index) => (
                        <div key={index} style={{ padding: '10px 12px', background: 'var(--s2)', borderRadius: 12, border: '1px solid var(--b)' }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--tp)' }}>{item.entity}</div>
                          <div style={{ fontSize: 11, color: 'var(--tm)' }}>{item.entity_type} · {item.period}</div>
                          <div style={{ fontSize: 12, color: 'var(--tp)' }}>Risk: {item.predicted_risk} · Confidence: {item.confidence}%</div>
                        </div>
                      )) : (
                        <div style={{ color: 'var(--tm)', fontSize: 12 }}>No recent predictions available from the backend yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Supply Chain Entity Summary</span></div>
          <div className="card-body" style={{ display: 'grid', gap: 16 }}>
            <div className="g2">
              {ENTITY_TYPES.map(entity => (
                <button key={entity} type="button" onClick={() => setSelectedEntity(entity)} className="agent-card" style={{ borderColor: selectedEntity === entity ? 'var(--blue)' : undefined, cursor: 'pointer' }}>
                  <div className="agent-body">
                    <div className="agent-name" style={{ marginBottom: 6 }}>{entity}</div>
                    <div className="agent-metrics" style={{ gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div><div className="agent-metric-lbl">Count</div><div className="agent-metric-val">{entityCounts[entity]?.toLocaleString() ?? 0}</div></div>
                      <div><div className="agent-metric-lbl">Health</div><div className="agent-metric-val">{entityHealth[entity]}</div></div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
            <div className="card" style={{ padding: 18, background: 'var(--s2)', borderColor: 'var(--b)' }}>
              <div className="section-lbl">Entity Information Panel</div>
              <div style={{ display: 'grid', gap: 12 }}>
                <div><strong style={{ color: 'var(--tp)' }}>{selectedEntity}</strong> is represented in the backend knowledge graph and associated with one or more intelligent agents supporting decision workflows.</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div><div className="agent-metric-lbl">Relationship Count</div><div className="agent-metric-val">{graph.total_connections?.toLocaleString() ?? 0}</div></div>
                  <div><div className="agent-metric-lbl">Associated Agent</div><div className="agent-metric-val">{entityAgentMap[selectedEntity]}</div></div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div><div className="agent-metric-lbl">Latest AI Prediction</div><div className="agent-metric-val">{forecast.high_risk_count != null ? `${forecast.high_risk_count} high risk entries` : 'Pending'}</div></div>
                  <div><div className="agent-metric-lbl">Connected Nodes</div><div className="agent-metric-val">{graph.top_connected_entities?.length ?? 0}</div></div>
                </div>
                <div><div className="agent-metric-lbl">Business Metrics</div><div className="agent-metric-val">{system.data_coverage?.total_records?.toLocaleString() ?? 0} records · {system.data_coverage?.entities_tracked ?? 0} entities tracked</div></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><span className="card-title">Backend Workflow Timeline</span></div>
        <div className="card-body" style={{ display: 'grid', gap: 18 }}>
          <div className="steps" style={{ gap: 12, flexWrap: 'wrap' }}>
            {TIMELINE_STEPS.map(step => (
              <div key={step.id} className={`step ${step.status}`}>
                <div className="step-num">{step.index}</div>
                <div className="step-label">{step.label}</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
              <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 14, border: '1px solid var(--b)' }}>
                <div className="section-lbl">Current System Stage</div>
                <div style={{ color: 'var(--tp)', fontWeight: 600 }}>{timelineCurrentStage}</div>
              </div>
              <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 14, border: '1px solid var(--b)' }}>
                <div className="section-lbl">Training Status</div>
                <div style={{ color: 'var(--tp)', fontWeight: 600 }}>{system.initialized ? 'Complete' : 'Pending'}</div>
              </div>
              <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 14, border: '1px solid var(--b)' }}>
                <div className="section-lbl">Workflow Source</div>
                <div style={{ color: 'var(--tp)', fontWeight: 600 }}>Dataset → Feature Engineering → Multi-Agent AI → Knowledge Graph</div>
              </div>
            </div>
            <div>
              <div className="section-lbl">Recent Backend Activities</div>
              <div style={{ display: 'grid', gap: 10 }}>
                {recentActivities.length > 0 ? recentActivities.map((item, index) => (
                  <div key={index} style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--s2)', border: '1px solid var(--b)' }}>
                    <div style={{ fontSize: 13, color: 'var(--tp)', fontWeight: 600 }}>{item.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--tm)' }}>{item.value}</div>
                  </div>
                )) : (
                  <div style={{ color: 'var(--tm)', fontSize: 12 }}>No backend activity events are available yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
