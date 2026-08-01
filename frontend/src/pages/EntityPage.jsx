/**
 * EntityPage.jsx — Entity Intelligence Dashboard
 * Fully integrated with Live Operations backend APIs (/api/v1/business/live-ops).
 * All numbers, charts, normalized weighted risk, and timelines derived dynamically.
 */

import { useState, useMemo, useEffect } from 'react'
import { api } from '../api/client'
import {
  useLiveOpsEntities,
  useLiveOpsEntityAnalytics,
} from '../hooks/useSupplyChainData'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Cell, Legend, PieChart, Pie,
} from 'recharts'
import {
  Layers, Search, TrendingUp, TrendingDown,
  Activity, Shield, Target, Lightbulb, RefreshCw,
} from 'lucide-react'
import styles from './EntityPage.module.css'
import { useSharedParams } from '../hooks/useSharedParams'

const TYPES = [
  { key: 'Supplier',   label: 'Supplier',   icon: '🏭', color: '#e5534b' },
  { key: 'Warehouse',  label: 'Warehouse',  icon: '🏪', color: '#d4a017' },
  { key: 'Product',    label: 'Product',    icon: '📦', color: '#3fb950' },
  { key: 'Shipment',   label: 'Shipment',   icon: '🚚', color: '#5b8aff' },
  { key: 'Customer',   label: 'Customer',   icon: '👤', color: '#7c6fcd' },
]

function cleanNodeId(nodeId) {
  if (!nodeId) return 'Unknown Entity'
  let s = nodeId.replace(/^(supplier|product|warehouse|shipment|customer|order|event)[_-]/i, '')
  s = s.replace(/[_-]main$/i, '')
  s = s.replace(/[_-]/g, ' ')
  return s.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className={styles.tooltipWrap}>
      {label && <div className={styles.tooltipLabel}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className={styles.tooltipRow}>
          <div className={styles.tooltipColor} style={{ background: p.color || p.stroke }} />
          <span style={{ color: 'var(--ts)' }}>{p.name}:</span>
          <span className={styles.tooltipVal}>
            {typeof p.value === 'number'
              ? p.name.includes('$') || p.name.includes('Exposure') || p.name.includes('Margin') || p.name.includes('Cost')
                ? `$${p.value.toLocaleString()}`
                : p.value.toLocaleString()
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function EntityPage() {
  const { type, entityId, setParams, navigateToPage } = useSharedParams()
  const selectedType = type || 'Supplier'
  const selectedEntityId = entityId || ''
  const [search, setSearch] = useState('')

  // ── Backend Live Operations Hooks ─────────────────────────────────
  const entityListQuery = useLiveOpsEntities({
    entity_type: selectedType,
    search: search,
  })

  const nodeList = entityListQuery.data?.entities || []

  // Auto-select first entity if none selected
  useEffect(() => {
    if (nodeList.length > 0 && !selectedEntityId) {
      setParams({ entityId: nodeList[0].id })
    }
  }, [nodeList, selectedEntityId, setParams])

  const handleTypeChange = (newType) => {
    setParams({ type: newType, entityId: '' })
    setSearch('')
  }

  const analyticsQuery = useLiveOpsEntityAnalytics({
    entity_id: selectedEntityId,
    entity_type: selectedType,
  })

  const analytics = analyticsQuery.data || {}
  const kpis = analytics.kpis || {}
  const charts = analytics.charts || {}

  const activeEntity = useMemo(() => {
    return nodeList.find(n => n.id === selectedEntityId) || {
      name: analytics.entity_name || cleanNodeId(selectedEntityId),
      risk_score: kpis.risk_pct || 0,
      normalized_weighted_risk: 0,
    }
  }, [nodeList, selectedEntityId, analytics, kpis])

  const riskScore = (kpis.risk_pct || 0) / 100.0
  const accuracyScore = (kpis.forecast_accuracy_pct || 85.0) / 100.0

  const aiRecommendation = useMemo(() => {
    if (riskScore >= 0.65) {
      return `CRITICAL RISK ALERT: "${activeEntity.name}" exhibits elevated supply disruption metrics. We recommend reallocating order volumes by 20% to backup suppliers.`
    }
    if (riskScore >= 0.35) {
      return `MODERATE VOLATILITY: Volatility thresholds exceeded for "${activeEntity.name}". Adjust safety stock buffer by +15% prior to next forecast period.`
    }
    return `STABLE OPERATIONS: "${activeEntity.name}" displays optimal SLA compliance (${kpis.sla_pct}%). Holding costs can be optimized.`
  }, [riskScore, activeEntity.name, kpis.sla_pct])

  const axisStyle = { fontSize: '8px', fill: 'var(--tm)' }

  return (
    <div className={styles.page}>
      
      {/* ── LEFT PANEL ── */}
      <div className={styles.leftPanel}>
        <div className={styles.leftHeader}>
          <div className={styles.title}>Entity Explorer</div>
          
          <div className={styles.typeTabs}>
            {TYPES.map(t => (
              <button
                key={t.key}
                onClick={() => handleTypeChange(t.key)}
                className={`${styles.typeTab} ${selectedType === t.key ? styles.typeTabActive : ''}`}
                title={t.label}
              >
                {t.icon}
              </button>
            ))}
          </div>

          <div className={styles.searchWrap}>
            <Search size={12} className={styles.searchIcon} />
            <input
              className={styles.searchInput}
              placeholder={`Search ${selectedType.toLowerCase()}s…`}
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.listArea}>
          {nodeList.map(item => {
            const isActive = selectedEntityId === item.id
            const normRisk = item.normalized_weighted_risk || 0
            const riskColor = item.risk_score >= 65 ? '#d63031' : item.risk_score >= 35 ? '#e67e22' : '#00b894'

            return (
              <div
                key={item.id}
                onClick={() => setParams({ entityId: item.id })}
                className={`${styles.entityItem} ${isActive ? styles.entityItemActive : ''}`}
              >
                <div>
                  <div className={styles.entityItemName} style={{ color: isActive ? 'var(--blue)' : 'var(--tp)' }}>{item.name}</div>
                  <div className={styles.entityItemSub}>
                    Orders: {item.total_orders?.toLocaleString()}
                  </div>
                </div>
                <span
                  className={styles.entityItemBadge}
                  style={{ background: `${riskColor}12`, color: riskColor }}
                >
                  {normRisk.toFixed(1)}%
                </span>
              </div>
            )
          })}
          {nodeList.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--tm)', fontSize: '11px', padding: '16px 0' }}>
              No instances found
            </div>
          )}
        </div>
      </div>

      {/* ── CENTER REPORT CANVAS ── */}
      <div className={styles.canvas}>
        {!selectedEntityId ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIconBox}>
              <Layers size={28} style={{ color: 'var(--blue)' }} />
            </div>
            <h3 className={styles.emptyTitle}>Executive Entity Analyzer</h3>
            <p className={styles.emptyDesc}>
              Select an entity instance from the left sidebar to generate a complete multi-dimensional executive dashboard.
            </p>
          </div>
        ) : (
          <>
            {/* Super Header */}
            <div className={styles.reportHeader}>
              <div className={styles.headerTitleBox}>
                <div
                  className={styles.headerIconBox}
                  style={{
                    background: `${TYPES.find(t => t.key === selectedType)?.color}15`,
                    color: TYPES.find(t => t.key === selectedType)?.color
                  }}
                >
                  {TYPES.find(t => t.key === selectedType)?.icon}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div className={styles.reportTitle}>{activeEntity.name}</div>
                    <button
                      onClick={() => navigateToPage('/graph', { entityId: selectedEntityId })}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '4px',
                        background: 'rgba(9,132,227,0.08)', color: 'var(--blue)',
                        border: '1px solid rgba(9,132,227,0.2)', borderRadius: '4px',
                        padding: '2px 8px', fontSize: '9.5px', fontWeight: 600, cursor: 'pointer'
                      }}
                    >
                      <Activity size={10} />
                      View Relationships ({kpis.relationship_count || 0})
                    </button>
                  </div>
                  <div className={styles.reportSub}>
                    Fulfillment Level · {selectedType} Class Analysis
                  </div>
                </div>
              </div>

              {/* Gauges */}
              <div className={styles.headerGauges}>
                <div className={styles.headerGauge}>
                  <div className={styles.gaugeVal} style={{ color: riskScore >= 0.65 ? '#d63031' : riskScore >= 0.35 ? '#e67e22' : '#00b894' }}>
                    {kpis.risk_pct || 0}%
                  </div>
                  <div className={styles.gaugeLabel}>Risk Level</div>
                </div>
                <div className={styles.headerGauge}>
                  <div className={styles.gaugeVal} style={{ color: '#00b894' }}>
                    {kpis.forecast_accuracy_pct || 0}%
                  </div>
                  <div className={styles.gaugeLabel}>Forecast Accuracy</div>
                </div>
              </div>
            </div>

            <div className={styles.canvasContent}>
              {/* KPIs */}
              <div className={styles.kpiGrid}>
                {[
                  { label: 'Estimated Financial Exposure', value: `$${kpis.financial_exposure?.toLocaleString() || 0}`, color: '#d63031', desc: 'Financial loss exposure' },
                  { label: 'Lead Time Delay', value: `${kpis.lead_time_delay || 0} Days`, color: '#e67e22', desc: 'Projected shipping delta' },
                  { label: 'Knowledge Graph Connections', value: kpis.knowledge_graph_connections || 0, color: 'var(--blue)', desc: 'Neo4j degree count' },
                  { label: 'Service Level Agreement', value: `${kpis.sla_pct || 0}%`, color: (kpis.sla_pct || 0) >= 80 ? '#00b894' : '#d63031', desc: 'Performance SLA rating' },
                ].map((kpi, idx) => (
                  <div key={idx} className={styles.kpiCard} style={{ borderTop: `3px solid ${kpi.color}` }}>
                    <div className={styles.kpiLabel}>{kpi.label}</div>
                    <div className={styles.kpiValue} style={{ color: kpi.color }}>{kpi.value}</div>
                    <div className={styles.kpiDesc}>{kpi.desc}</div>
                  </div>
                ))}
              </div>

              {/* AI Recommendation Banner */}
              <div className={styles.recommendationCard}>
                <div className={styles.recIconBox}>
                  <Lightbulb size={16} />
                </div>
                <div>
                  <div className={styles.recTitle}>AI Optimization Plan</div>
                  <div className={styles.recText}>{aiRecommendation}</div>
                </div>
              </div>

              {/* 8 Charts Grid */}
              <div className={styles.chartsGrid}>
                
                {/* 1. Lead Time Performance Trend */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Activity size={12} style={{ color: 'var(--blue)' }} />
                    <span className={styles.chartTitle}>Lead Time Performance Trend</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={charts.lead_time_trend || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="month" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                        <Tooltip content={<ChartTip />} />
                        <Line type="monotone" dataKey="average_lead_time" name="Avg Delay Days" stroke="var(--blue)" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 2. Operational Risk Trend */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Shield size={12} style={{ color: '#d63031' }} />
                    <span className={styles.chartTitle}>Operational Risk Component Trend</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={charts.operational_risk_trend || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="month" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                        <Tooltip content={<ChartTip />} />
                        <Area type="monotone" dataKey="prediction_risk" name="Prediction Risk %" stackId="1" stroke="#d63031" fill="#d63031" fillOpacity={0.12} />
                        <Area type="monotone" dataKey="actual_risk" name="Actual Risk %" stackId="1" stroke="#e67e22" fill="#e67e22" fillOpacity={0.12} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 3. Forecast Deviation Timeline */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Target size={12} style={{ color: '#00b894' }} />
                    <span className={styles.chartTitle}>Forecast Deviation Timeline</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={charts.forecast_deviation_timeline || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="month" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                        <Tooltip content={<ChartTip />} />
                        <Line type="monotone" dataKey="actual" name="Actual Performance" stroke="var(--blue)" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="forecast" name="Predicted Forecast" stroke="#00b894" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 4. Historical Operations Volume */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <TrendingUp size={12} style={{ color: 'var(--ts)' }} />
                    <span className={styles.chartTitle}>Historical Operations Volume</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={charts.historical_operations_volume || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="month" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                        <Tooltip content={<ChartTip />} />
                        <Area type="monotone" dataKey="orders" name="Historical Order Count" stroke="var(--blue)" fill="var(--blue)" fillOpacity={0.06} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 5. Relationship Distribution */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Layers size={12} style={{ color: '#7c6fcd' }} />
                    <span className={styles.chartTitle}>Relationship Connection Strengths</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={charts.relationship_distribution || []}
                          dataKey="value"
                          cx="50%" cy="50%"
                          innerRadius={22} outerRadius={42}
                          paddingAngle={3}
                        >
                          {(charts.relationship_distribution || []).map((d, i) => <Cell key={i} fill={d.color} />)}
                        </Pie>
                        <Tooltip content={<ChartTip />} />
                        <Legend iconSize={6} iconType="circle" wrapperStyle={{ fontSize: 9 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 6. Connected Entities */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Layers size={12} style={{ color: '#5b8aff' }} />
                    <span className={styles.chartTitle}>Network Connected Entities</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={charts.connected_entities || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                        <Tooltip content={<ChartTip />} />
                        <Bar dataKey="count" name="Connection Count" fill="var(--blue)" radius={[3, 3, 0, 0]} barSize={20}>
                          {(charts.connected_entities || []).map((entry, idx) => (
                            <Cell key={`cell-${idx}`} fill={['#3fb950', '#d4a017', '#5b8aff', '#7c6fcd'][idx % 4]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 7. Business Impact Radar */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <TrendingDown size={12} style={{ color: '#e67e22' }} />
                    <span className={styles.chartTitle}>Exposed Risk Radar Dimensions</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={charts.business_impact_radar || []} cx="50%" cy="50%" outerRadius={38}>
                        <PolarGrid stroke="var(--b)" />
                        <PolarAngleAxis dataKey="name" tick={{ fontSize: 7.5, fill: 'var(--ts)' }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8, fill: 'var(--tm)' }} />
                        <Radar name="Severity Ratio" dataKey="value" stroke="#e67e22" fill="#e67e22" fillOpacity={0.25} />
                        <Tooltip content={<ChartTip />} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 8. Monthly Comparison */}
                <div className={styles.chartCard}>
                  <div className={styles.chartTitleBox}>
                    <Activity size={12} style={{ color: '#00b894' }} />
                    <span className={styles.chartTitle}>Fulfillment Comparison Rating</span>
                  </div>
                  <div className={styles.chartPane}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={charts.monthly_comparison || []} margin={{ left: -22, right: 6, top: 4, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                        <XAxis dataKey="period" tick={axisStyle} axisLine={false} tickLine={false} />
                        <YAxis tick={axisStyle} axisLine={false} tickLine={false} domain={[50, 100]} />
                        <Tooltip content={<ChartTip />} />
                        <Legend iconSize={7} wrapperStyle={{ fontSize: 9 }} />
                        <Bar dataKey="current_month" name="Current Month" fill="var(--blue)" radius={[2, 2, 0, 0]} />
                        <Bar dataKey="last_month" name="Last Month" fill="#00b894" radius={[2, 2, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>
            </div>
          </>
        )}
      </div>

    </div>
  )
}
