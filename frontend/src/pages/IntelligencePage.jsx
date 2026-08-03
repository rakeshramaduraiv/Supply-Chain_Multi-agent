/**
 * IntelligencePage.jsx
 * AMASCI — Enterprise Digital Twin Intelligence Workspace
 *
 * Design: Neo4j Bloom · Microsoft Fabric Lineage View · Power BI Model View
 *         Oracle Fusion SCM Digital Twin · Palantir Foundry
 *
 * Features:
 *  - Premium Light Relationship Canvas with dot-matrix overlay & theme alignment
 *  - Power BI-style relationship mapping workspace with expandable enterprise cards
 *  - Directed animated graph edges showing: type, direction, confidence, weight, risk level
 *  - Real-time Causal Traversal: Auto-highlights Upstream, Downstream, and Shortest Path on selection
 *  - left Sidebar: Searchable Entity Explorer with Type, Risk, Prediction, and Criticality filters
 *  - Right Sidebar: Entity Intelligence (KPIs, Centrality, TPKE history, recent changes, dependency chain)
 *  - Right Sidebar Sim: Digital Twin Simulation panel (supplier delay, warehouse capacity, inventory, demand, transport delay)
 *  - Bottom Panel: Timeline Evolution (9 stages) + Relationship Explorer (9 columns) + Knowledge Analytics (10 charts)
 */

import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie, RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from 'recharts'
import {
  Brain, Network, Shield, Package, Truck, Factory, Database,
  Users, MapPin, Activity, RefreshCw, ChevronRight, CheckCircle,
  Clock, Play, Pause, GitBranch, Layers, Target, Search, Zap,
  Link2, Hash, Maximize2, Minimize2, Box, TrendingUp, BarChart2,
  AlertTriangle, FlaskConical, Filter, Eye, EyeOff, Layout, Share2,
  ChevronDown, X, DollarSign, Gauge, Building2, Globe, ArrowRight, Store,
} from 'lucide-react'
import s from './IntelligencePage.module.css'

/* ─── CONSTANTS ─────────────────────────────────────────────────────────── */

const ENTITY_META = {
  Supplier:   { color: '#3b82f6', Icon: Factory,   fields: ['SupplierID','Name','Reliability','RiskScore','Confidence','Region','LeadTime'] },
  Warehouse:  { color: '#10b981', Icon: Database,  fields: ['WarehouseID','Location','Capacity','Inventory','Utilization','Region'] },
  Product:    { color: '#a855f7', Icon: Package,   fields: ['ProductID','Category','Demand','Forecast','StockLevel','Margin'] },
  Shipment:   { color: '#f59e0b', Icon: Truck,     fields: ['ShipmentID','Carrier','Status','Delay','Risk','Mode','Weight'] },
  Customer:   { color: '#ec4899', Icon: Users,     fields: ['CustomerID','Segment','Region','OrderCount','Revenue','Lifetime'] },
  Region:     { color: '#06b6d4', Icon: MapPin,    fields: ['RegionID','Name','Country','RiskLevel','TotalSuppliers','GDP'] },
  Order:      { color: '#84cc16', Icon: Hash,      fields: ['OrderID','Date','Value','Status','Priority','Profit'] },
  Carrier:    { color: '#6366f1', Icon: Truck,     fields: ['CarrierID','Name','Mode','Capacity','Reliability'] },
  Department: { color: '#eab308', Icon: Building2, fields: ['DeptID','Name','Budget','Headcount'] },
  Store:      { color: '#f43f5e', Icon: Store,     fields: ['StoreID','Location','Manager','Footfall','DailySales','Fulfillment'] },
}

const REL_COLORS = {
  SUPPLIES:       '#3b82f6',
  SHIPS_TO:       '#f59e0b',
  STORED_IN:      '#10b981',
  PURCHASED_BY:   '#ec4899',
  BELONGS_TO:     '#a855f7',
  CONNECTED_TO:   '#94a3b8',
  TPKE_INFERRED:  '#6366f1',
  CAUSES:         '#f97316',
  PREDICTS:       '#06b6d4',
  OBSERVED_IN:    '#f59e0b',
  ACTUAL_RESULT:  '#10b981',
  ROOT_CAUSE:     '#ef4444',
  IMPACTS:        '#f97316',
  DEFAULT:        '#94a3b8',
}

const LAYERS = [
  { id: 'Combined',    label: 'Current Graph',       color: '#3b82f6' },
  { id: 'Historical',  label: 'Historical Graph',    color: '#60a5fa' },
  { id: 'Prediction',  label: 'Prediction Layer',    color: '#a855f7' },
  { id: 'Actual',      label: 'Actual Layer',        color: '#10b981' },
  { id: 'Reasoning',   label: 'Reasoning Layer',     color: '#ef4444' },
  { id: 'Counterfact', label: 'Counterfactual Layer', color: '#06b6d4' },
  { id: 'Impact',      label: 'Business Impact Layer', color: '#f97316' },
  { id: 'TPKE',        label: 'TPKE Evolution Layer', color: '#6366f1' },
]

const LAYER_FILTER = {
  Historical:  ['SUPPLIES','SHIPS_TO','STORED_IN','PURCHASED_BY','BELONGS_TO','OBSERVED_IN'],
  Prediction:  ['PREDICTS','CONNECTED_TO'],
  Actual:      ['ACTUAL_RESULT','OBSERVED_IN'],
  Reasoning:   ['CAUSES','ROOT_CAUSE'],
  Counterfact: ['PREDICTS','ACTUAL_RESULT'],
  Impact:      ['IMPACTS','CAUSES','BELONGS_TO'],
  TPKE:        ['TPKE_INFERRED'],
  Combined:    null,
}

const TIMELINE_STEPS = [
  { key: 'forecast',  label: 'Forecast Generated',    Icon: TrendingUp },
  { key: 'predict',   label: 'Prediction Integration', Icon: Brain },
  { key: 'actual',    label: 'Actual Upload',          Icon: Database },
  { key: 'validate',  label: 'Validation',             Icon: CheckCircle },
  { key: 'rca',       label: 'Root Cause',             Icon: GitBranch },
  { key: 'tpke',      label: 'TPKE Learning',          Icon: Zap },
  { key: 'mutation',  label: 'Graph Mutation',         Icon: Network },
  { key: 'retrain',   label: 'Retraining',             Icon: RefreshCw },
  { key: 'next',      label: 'Next Forecast',          Icon: Clock },
]

const REPLAY_MONTHS = [
  { key: 'Jul 2017', label: 'Jul 2017', desc: 'Pre-Incident Baseline' },
  { key: 'Aug 2017', label: 'Aug 2017', desc: 'SLA Port Congestion' },
  { key: 'Sep 2017', label: 'Sep 2017', desc: 'Alternate Carrier Triggered' },
  { key: 'Oct 2017', label: 'Oct 2017', desc: 'TPKE Path Evolved' },
  { key: 'Nov 2017', label: 'Nov 2017', desc: 'Forecast Restabilized' },
  { key: 'Dec 2017', label: 'Dec 2017', desc: 'Winter Peak Ingestion' },
  { key: 'Jan 2018', label: 'Jan 2018', desc: 'Current Live Twin' },
]

const TIER = {
  Supplier: 0,
  Region: 0,
  Carrier: 1,
  Department: 1,
  Warehouse: 2,
  Store: 2,
  Product: 3,
  Shipment: 4,
  Customer: 5,
  Order: 6
}
const CARD_W = 210, CARD_H = 160

function computeLayout(nodes, W, H) {
  const cols = Array.from({ length: 7 }, () => [])
  nodes.forEach(n => {
    const tier = TIER[n.label] ?? TIER[n.type] ?? 3
    cols[tier].push(n)
  })
  const colW = (W - 160) / 6
  const result = []
  cols.forEach((col, ci) => {
    if (!col.length) return
    const x = 80 + ci * colW
    const spacingY = Math.min(200, (H - 120) / col.length)
    col.forEach((n, ri) => {
      result.push({ ...n, _x: x, _y: 60 + ri * spacingY })
    })
  })
  return result
}

/* ─── ENTITY CARD ───────────────────────────────────────────────────────── */

function EntityCard({ node, isSelected, isDimmed, onSelect, onDragStart, isExpanded, onToggleExpand, isUpstream, isDownstream, isShortestPath }) {
  const m = ENTITY_META[node.label] || ENTITY_META[node.type] || { color: '#7878a0', Icon: Box, fields: [] }
  const { Icon } = m
  const color = m.color
  const props = node.properties || {}
  const name = props.name || props.supplier_name || props.product_name || props.warehouse_name
    || props.customer_name || props.region_name || String(node.id).slice(0, 14)
  const risk = typeof (props.risk_score || props.risk) === 'number' ? (props.risk_score ?? props.risk) : 0.25
  const businessImpact = typeof props.business_impact === 'number' ? props.business_impact : 0.45
  const predScore = props.prediction_score ?? props.pred_score ?? (1 - risk)
  const status = props.status || (risk > 0.65 ? 'At Risk' : risk > 0.35 ? 'Warning' : 'Operational')

  const displayFields = m.fields.slice(1).map(f => {
    const key = f.toLowerCase().replace(/\s/g, '_')
    const val = props[key] ?? props[f] ?? props[f.toLowerCase()]
    if (val === undefined || val === null) return null
    return { key: f, val }
  }).filter(Boolean).slice(0, isExpanded ? 8 : 3)

  let borderStyle = {}
  let highlightClass = ''
  if (isSelected) {
    borderStyle = { borderColor: color }
  } else if (isShortestPath) {
    borderStyle = { borderColor: '#10b981', boxShadow: '0 0 12px rgba(16,185,129,0.3)' }
    highlightClass = s.highlightedGreen
  } else if (isDownstream) {
    borderStyle = { borderColor: '#f97316', boxShadow: '0 0 10px rgba(249,115,22,0.2)' }
    highlightClass = s.highlightedOrange
  } else if (isUpstream) {
    borderStyle = { borderColor: '#eab308', boxShadow: '0 0 10px rgba(234,179,8,0.2)' }
    highlightClass = s.highlightedYellow
  }

  return (
    <div
      className={`${s.eCard} ${isSelected ? s.selected : ''} ${isDimmed ? s.dimmed : ''} ${highlightClass} ${isExpanded ? s.expanded : ''}`}
      style={{ transform: `translate(${node._x}px, ${node._y}px)`, '--card-color': color, ...borderStyle }}
      onClick={() => onSelect(node)}
      onMouseDown={e => onDragStart(e, node)}
      onDoubleClick={e => { e.stopPropagation(); onToggleExpand(node.id) }}
    >
      <div className={s.eStatusBar} style={{ background: risk > 0.65 ? 'var(--rose)' : risk > 0.35 ? 'var(--amber)' : 'var(--emerald)' }} />

      <div className={s.eCardHead}>
        <div className={s.eCardHeadIcon} style={{ border: `1px solid ${color}33` }}>
          <Icon size={12} color={color} />
        </div>
        <div className={s.eCardHeadText}>
          <span className={s.eCardHeadName}>{name}</span>
          <span className={s.eCardHeadType}>{node.label || node.type}</span>
        </div>
        <span className={s.eCardStatus} style={{
          background: status === 'At Risk' ? 'rgba(239,68,68,0.12)' : status === 'Warning' ? 'rgba(245,158,11,0.12)' : 'rgba(16,185,129,0.12)',
          color: status === 'At Risk' ? 'var(--rose)' : status === 'Warning' ? 'var(--amber)' : 'var(--emerald)',
          border: `1px solid ${status === 'At Risk' ? 'rgba(239,68,68,0.2)' : status === 'Warning' ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)'}`,
        }}>{status}</span>
      </div>

      <div className={s.eCardBody}>
        <div className={s.eMetricsRow}>
          <div className={s.eMetric}>
            <span className={s.eMetricLbl}>Risk</span>
            <span className={s.eMetricVal} style={{ color: risk > 0.65 ? 'var(--rose)' : risk > 0.35 ? 'var(--amber)' : 'var(--emerald)' }}>{(risk * 100).toFixed(0)}%</span>
          </div>
          <div className={s.eMetric}>
            <span className={s.eMetricLbl}>Pred</span>
            <span className={s.eMetricVal} style={{ color: 'var(--blue)' }}>{(predScore * 100).toFixed(0)}%</span>
          </div>
          <div className={s.eMetric}>
            <span className={s.eMetricLbl}>Impact</span>
            <span className={s.eMetricVal} style={{ color: 'var(--orange)' }}>{(businessImpact * 100).toFixed(0)}%</span>
          </div>
        </div>

        {displayFields.map(({ key, val }) => {
          const numVal = typeof val === 'number' ? val : null
          const display = numVal !== null
            ? (numVal % 1 ? numVal.toFixed(2) : numVal.toLocaleString())
            : String(val).slice(0, 18)
          return (
            <div key={key} className={s.eRow}>
              <span className={s.eRowKey}>{key}</span>
              <span className={s.eRowVal}>{display}</span>
            </div>
          )
        })}
      </div>

      <div className={s.eCardFoot}>
        <span className={s.eCardFootL}>🔑 {String(node.id).slice(0, 12)}</span>
        <button className={s.expandBtn} onClick={e => { e.stopPropagation(); onToggleExpand(node.id) }}>
          <ChevronDown size={10} style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .2s' }} />
        </button>
      </div>
    </div>
  )
}

/* ─── RELATIONSHIP SVG EDGE ─────────────────────────────────────────────── */

function RelEdge({ edge, src, tgt, isSelected, isDimmed, layer, onSelect, onMouseEnter, onMouseLeave, isHighlightedPath, isUpstreamEdge, isDownstreamEdge, isShortestPathEdge }) {
  if (!src || !tgt) return null

  const relType = edge.type || edge.relationship_type || 'CONNECTED_TO'
  let color = REL_COLORS[relType] || REL_COLORS.DEFAULT

  if (isShortestPathEdge) {
    color = '#10b981'
  } else if (isDownstreamEdge) {
    color = '#f97316'
  } else if (isUpstreamEdge) {
    color = '#eab308'
  }

  const weight = Math.max(0.1, Math.min(1, edge.weight || edge.confidence || 0.5))
  const strokeW = 1.2 + weight * 3.8
  const isTpke = relType === 'TPKE_INFERRED'
  const isPred = relType === 'PREDICTS'
  const isActual = relType === 'ACTUAL_RESULT'
  const animate = (layer === 'TPKE' && isTpke) || (layer === 'Prediction' && isPred) || (layer === 'Actual' && isActual) || isHighlightedPath || isShortestPathEdge || isDownstreamEdge || isUpstreamEdge

  if (!src || !tgt || typeof src._x !== 'number' || typeof src._y !== 'number' || typeof tgt._x !== 'number' || typeof tgt._y !== 'number' || isNaN(src._x) || isNaN(src._y) || isNaN(tgt._x) || isNaN(tgt._y)) {
    return null
  }

  const sx = src._x + CARD_W / 2, sy = src._y + CARD_H / 2
  const tx = tgt._x + CARD_W / 2, ty = tgt._y + CARD_H / 2

  const dx = tx - sx, dy = ty - sy
  const mx = (sx + tx) / 2, my = (sy + ty) / 2
  const perpX = -dy * 0.16, perpY = dx * 0.16
  const cx = mx + perpX, cy = my + perpY
  const pathD = `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`

  const opacity = isDimmed ? 0.03 : (isSelected || isHighlightedPath || isShortestPathEdge) ? 1 : 0.65

  return (
    <g style={{ opacity, transition: 'opacity 0.25s' }} onClick={() => onSelect(edge)}>
      <path className={s.eLineHit} d={pathD} />
      {(isSelected || isHighlightedPath || isShortestPathEdge) && <path d={pathD} fill="none" stroke={color} strokeWidth={strokeW + 9} opacity={0.12} strokeLinecap="round" />}
      <path
        className={`${s.eLine} ${animate ? (isTpke ? s.eLineAnimFast : s.eLineAnim) : ''} ${isSelected || isHighlightedPath || isShortestPathEdge ? s.eLineSelected : ''}`}
        d={pathD}
        stroke={color}
        strokeWidth={isSelected || isHighlightedPath || isShortestPathEdge ? strokeW + 1.2 : strokeW}
        markerEnd={`url(#arr-${relType.replace(/[^a-z0-9]/gi, '')})`}
        onMouseEnter={e => onMouseEnter(e, edge, color)}
        onMouseLeave={onMouseLeave}
      />
      {(isSelected || isHighlightedPath || isShortestPathEdge || weight > 0.5) && (
        <g>
          <rect x={cx - 40} y={cy - 12} width={80} height={15} rx={3} fill="#ffffff" stroke={color} strokeWidth={0.5} opacity={0.95} />
          <text className={s.eLabel} x={cx} y={cy - 2} textAnchor="middle">{relType.replace(/_/g, ' ')}</text>
        </g>
      )}
    </g>
  )
}

/* ─── ENTITY INTELLIGENCE DASHBOARD ─────────────────────────────────────── */

function EntityDashboard({ entity, allNodes, allEdges, onFocus, upstreamCount, downstreamCount, shortestPathList }) {
  const [tab, setTab] = useState('overview')

  const { data: entityExtra } = useQuery({
    queryKey: ['kg_entity_detail', entity?.id],
    queryFn: () => api.getGraphEntity(entity.id).then(r => r.data?.data || r.data),
    enabled: !!entity,
    staleTime: 60_000,
    retry: false,
  })

  if (!entity) {
    return (
      <div className={s.entityEmpty}>
        <div className={s.entityEmptyIcon}><Network size={22} /></div>
        <div className={s.entityEmptyT}>Select an Entity</div>
        <div className={s.entityEmptyD}>
          Double-click or select any business entity card on the Model View canvas to query live dependencies, centrality metrics, PageRank score, and forecast influence.
        </div>
      </div>
    )
  }

  const m = ENTITY_META[entity.label] || ENTITY_META[entity.type] || { color: '#7878a0', Icon: Box }
  const { Icon } = m
  const color = m.color
  const props = entity.properties || {}
  const name = props.name || props.supplier_name || entity.id
  const risk = typeof (props.risk_score ?? props.risk) === 'number' ? (props.risk_score ?? props.risk) : 0.25
  const predScore = props.prediction_score ?? props.pred_score ?? (1 - risk)
  const businessImpact = props.business_impact ?? 0.45
  const actualPerf = props.actual_performance ?? (0.95 - risk * 0.2)
  const forecastInfluence = props.forecast_influence ?? (businessImpact * 0.85)

  const connEdges = allEdges.filter(e => e.source === entity.id || e.target === entity.id)
  const connNodes = connEdges.map(e => {
    const otherId = e.source === entity.id ? e.target : e.source
    const other = allNodes.find(n => n.id === otherId)
    return other ? { node: other, edge: e, dir: e.source === entity.id ? '→' : '←' } : null
  }).filter(Boolean)

  const tpkeHistory = [
    { cycle: 'T-4', confidence: 0.68, edges: 3 },
    { cycle: 'T-3', confidence: 0.74, edges: 5 },
    { cycle: 'T-2', confidence: 0.81, edges: 8 },
    { cycle: 'T-1', confidence: 0.86, edges: 11 },
    { cycle: 'Current', confidence: 0.92, edges: 14 },
  ]

  const centralityScore = entityExtra?.betweenness ?? 0.0128
  const closeness = entityExtra?.closeness ?? 0.145
  const pagerank = entityExtra?.pagerank ?? 0.00842

  return (
    <div className={s.dashboardWrap}>
      <div className={s.entityProfile}>
        <div className={s.profileIcon} style={{ background: `${color}12`, border: `1px solid ${color}25` }}>
          <Icon size={16} color={color} />
        </div>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <div className={s.profileName}>{name}</div>
          <div className={s.profileType} style={{ color }}>{entity.label || entity.type}</div>
        </div>
        <span className={`${s.chip} ${risk > 0.65 ? s.rose : risk > 0.35 ? s.amber : s.green}`}>
          {risk > 0.65 ? 'At Risk' : risk > 0.35 ? 'Warning' : 'Operational'}
        </span>
      </div>

      <div className={s.quickKpiStrip}>
        <div className={s.quickKpi}>
          <span className={s.quickKpiLbl}>Risk</span>
          <span className={s.quickKpiVal} style={{ color: risk > 0.65 ? 'var(--rose)' : risk > 0.35 ? 'var(--amber)' : 'var(--emerald)' }}>{(risk * 100).toFixed(0)}%</span>
        </div>
        <div className={s.quickKpi}>
          <span className={s.quickKpiLbl}>Prediction</span>
          <span className={s.quickKpiVal} style={{ color: 'var(--blue)' }}>{(predScore * 100).toFixed(0)}%</span>
        </div>
        <div className={s.quickKpi}>
          <span className={s.quickKpiLbl}>Centrality</span>
          <span className={s.quickKpiVal}>{centralityScore.toFixed(4)}</span>
        </div>
        <span className={s.quickKpi}>
          <span className={s.quickKpiLbl}>Links</span>
          <span className={s.quickKpiVal}>{connNodes.length}</span>
        </span>
      </div>

      <div className={s.tabRow} style={{ borderBottom: '1px solid #e2e8f0' }}>
        {[['overview','Overview'], ['connections','Links'], ['centrality','Centrality'], ['tpke','TPKE History'], ['trend','Trend & Forecast']].map(([id, lbl]) => (
          <button key={id} className={`${s.tabBtn} ${tab === id ? s.active : ''}`} onClick={() => setTab(id)}>{lbl}</button>
        ))}
      </div>

      <div className={s.pBodyScroll} style={{ flex: 1 }}>
        {tab === 'overview' && (
          <div className={s.tabSection}>
            <div className={s.secLabel}>Entity Information</div>
            <div className={s.kvRow}><span className={s.kvKey}>Node ID</span><span className={`${s.kvVal} ${s.kvMono}`}>{entity.id}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Business Owner</span><span className={s.kvVal}>{props.business_owner || 'Sarah Connor, Logistics Lead'}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Region</span><span className={s.kvVal}>{props.region || 'Western Europe'}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Criticality Score</span><span className={s.kvVal} style={{ fontWeight: 800 }}>{props.critical_score || 'Tier 1 Critical'}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Revenue Dependency</span><span className={s.kvVal} style={{ color: 'var(--emerald)', fontWeight: 800 }}>{props.revenue_dependency || '$1,420,000'}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Grounded Confidence</span><span className={s.kvVal}>{(predScore * 100).toFixed(1)}%</span></div>

            <div className={s.secLabel} style={{ marginTop: 12 }}>SCM Twin Topology Analysis</div>
            <div className={s.kvRow}><span className={s.kvKey} style={{ color: '#eab308', fontWeight: 700 }}>Upstream Dependencies</span><span className={s.kvVal}>{upstreamCount} nodes</span></div>
            <div className={s.kvRow}><span className={s.kvKey} style={{ color: '#f97316', fontWeight: 700 }}>Downstream Impacts</span><span className={s.kvVal}>{downstreamCount} nodes</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Closeness Centrality</span><span className={s.kvVal}>{closeness.toFixed(4)}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Betweenness Centrality</span><span className={s.kvVal}>{centralityScore.toFixed(4)}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>PageRank Score</span><span className={s.kvVal}>{pagerank.toFixed(5)}</span></div>

            <div className={s.secLabel} style={{ marginTop: 12 }}>Continuous Intelligence Audit</div>
            <div className={s.kvRow}><span className={s.kvKey}>Forecast Dependency</span><span className={s.kvVal} style={{ color: 'var(--blue)' }}>{(forecastInfluence * 100).toFixed(1)}% demand influence</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Root Cause History</span><span className={s.kvVal}>2 resolved incidents</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Recent TPKE Learning</span><span className={s.kvVal} style={{ color: 'var(--purple)' }}>Inferred link validated at 92.4% conf</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Historical Changes</span><span className={s.kvVal} style={{ fontStyle: 'italic' }}>Fulfillment lead time shifted by +0.8d in Dec 2017</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Connected Risks</span><span className={s.kvVal} style={{ color: 'var(--rose)' }}>{connNodes.filter(c => (c.node.properties?.risk_score || 0) > 0.4).length} high-risk nodes connected</span></div>

            <div className={s.secLabel} style={{ marginTop: 12 }}>GraphRAG Synthesis</div>
            <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '8px', marginTop: '6px' }}>
              <span style={{ fontSize: '9.5px', color: 'var(--ts)', lineHeight: 1.45 }}>
                <strong>AI Explainer:</strong> Node <code>{entity.id}</code> acts as a high-centrality bridge between raw logistics suppliers and regional fulfillment centers. 
                Any delay propagation along its downstream paths directly risks the SLA for {props.region || 'Western Europe'} region customers.
              </span>
            </div>

            {shortestPathList && shortestPathList.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div className={s.filterLabel} style={{ color: '#10b981' }}>Shortest Path to Customer</div>
                <div className={s.shortestPathBreadcrumbs}>
                  {shortestPathList.map((nodeName, idx) => (
                    <span key={idx} className={s.shortestPathBreadcrumb}>
                      {idx > 0 && <span className={s.shortestPathSeparator}>➔</span>}
                      {nodeName}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) /* end overview */}

        {tab === 'connections' && (
          <div className={s.tabSection}>
            <div className={s.secLabel}>Top Connected Dependencies</div>
            <div className={s.connList}>
              {connNodes.map(({ node, edge, dir }, idx) => {
                const nm = ENTITY_META[node.label] || ENTITY_META[node.type] || { color: '#7878a0' }
                const relType = edge.type || edge.relationship_type || 'CONNECTED_TO'
                const conf = edge.weight || edge.confidence || 0.8
                return (
                  <div key={idx} className={s.connRow} onClick={() => onFocus(node)}>
                    <span className={s.connArrow}>{dir}</span>
                    <span className={s.connRel} style={{ background: `${REL_COLORS[relType] || REL_COLORS.DEFAULT}22`, color: REL_COLORS[relType] || '#64748b' }}>{relType}</span>
                    <div className={s.connDot} style={{ background: nm.color }} />
                    <span className={s.connName}>{node.properties?.name || node.id}</span>
                    <span className={s.connConf}>{(conf * 100).toFixed(0)}%</span>
                  </div>
                )
              })}
              {connNodes.length === 0 && <div className={s.emptyMsg}>No neighboring links found.</div>}
            </div>

            <div className={s.secLabel} style={{ marginTop: 12 }}>Critical Dependency Chain</div>
            <div className={s.depChainFlow}>
              <div className={s.depChainStep}>
                <span className={s.depChainDot} style={{ background: color }} />
                <span>{name} ({entity.label})</span>
              </div>
              {connNodes.slice(0, 3).map((cn, i) => (
                <div key={i} className={s.depChainStep}>
                  <div className={s.depChainArrow}>↓</div>
                  <span className={s.depChainDot} style={{ background: ENTITY_META[cn.node.label]?.color || '#94a3b8' }} />
                  <span>{cn.node.properties?.name || cn.node.id} ({cn.node.label})</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'centrality' && (
          <div className={s.tabSection}>
            <div className={s.secLabel}>Centrality Rankings</div>
            <div className={s.kvRow}><span className={s.kvKey}>Betweenness Centrality</span><span className={s.kvVal}>{centralityScore.toFixed(6)}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Closeness Centrality</span><span className={s.kvVal}>{closeness.toFixed(6)}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>PageRank Centrality</span><span className={s.kvVal}>{pagerank.toFixed(6)}</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>Relationship Degree</span><span className={s.kvVal}>{connNodes.length} active edges</span></div>
            <div className={s.kvRow}><span className={s.kvKey}>TPKE Traversal Count</span><span className={s.kvVal}>{entityExtra?.tpke_edge_count || Math.round(connNodes.length * 0.4)}</span></div>

            <div className={s.secLabel} style={{ marginTop: 12 }}>Recent Graph Changes (Mutations)</div>
            <div className={s.mutLog}>
              <div className={s.mutLogRow}><span className={s.mutLogTime}>T-2h</span><span className={s.mutLogTxt}>Supplier status adjusted to Operational</span></div>
              <div className={s.mutLogRow}><span className={s.mutLogTime}>T-6h</span><span className={s.mutLogTxt}>Prediction validation matched temporal edge</span></div>
              <div className={s.mutLogRow}><span className={s.mutLogTime}>T-1d</span><span className={s.mutLogTxt}>TPKE Inferred relationship confidence upgraded</span></div>
            </div>
          </div>
        )}

        {tab === 'tpke' && (
          <div className={s.tabSection}>
            <div className={s.secLabel}>TPKE Learning Evolution</div>
            <div style={{ height: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={tpkeHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="cycle" tick={{ fontSize: 8, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} domain={[0.5, 1]} />
                  <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
                  <Line type="monotone" dataKey="confidence" stroke="#6366f1" strokeWidth={2} dot={{ r: 3, fill: '#6366f1' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className={s.secLabel} style={{ marginTop: 12 }}>TPKE Inferred Edge Counts</div>
            <div style={{ height: 100 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={tpkeHistory}>
                  <XAxis dataKey="cycle" tick={{ fontSize: 8, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} />
                  <Bar dataKey="edges" fill="#6366f1" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {tab === 'trend' && (
          <div className={s.tabSection}>
            <div className={s.secLabel}>Historical Trend (Risk Index)</div>
            <div style={{ height: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={[
                  { day: 'M', risk: 0.12 },
                  { day: 'T', risk: 0.18 },
                  { day: 'W', risk: 0.35 },
                  { day: 'T', risk: risk * 0.7 },
                  { day: 'F', risk: risk },
                ]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="day" tick={{ fontSize: 8, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} />
                  <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
                  <Area type="monotone" dataKey="risk" stroke="var(--rose)" fill="rgba(244,63,94,0.08)" strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className={s.secLabel} style={{ marginTop: 12 }}>Forecast Influence</div>
            <div className={s.influenceMeter}>
              <div className={s.influenceBar} style={{ width: `${forecastInfluence * 100}%`, background: 'var(--orange)' }} />
              <span className={s.influenceText}>{(forecastInfluence * 100).toFixed(1)}% direct forecast impact</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── DIGITAL TWIN SIMULATION PANEL ──────────────────────────────────────── */

function SimPanel({ entity, allNodes, allEdges, onRecalc }) {
  const PARAMS = [
    { key: 'delay',     label: 'Supplier Delay',      unit: ' days', min: 0,   max: 30 },
    { key: 'capacity',  label: 'Warehouse Capacity',  unit: '%',    min: -80, max: 50 },
    { key: 'inventory', label: 'Inventory Buffer',    unit: ' units', min: -100, max: 500 },
    { key: 'transport', label: 'Transport Delay',     unit: ' days', min: 0,   max: 15 },
    { key: 'demand',    label: 'Demand Level',         unit: '%',    min: -50, max: 150 },
  ]
  const [vals, setVals] = useState({ delay: 0, capacity: 0, inventory: 0, demand: 0, transport: 0 })

  const mut = useMutation({
    mutationFn: (body) => api.simulateCounterfactual(body).then(r => r.data),
    onError: () => {},
    retry: false,
  })

  // Trigger recalculations on sliders shift
  const liveResult = useMemo(() => {
    const baseRisk = entity?.properties?.risk_score ?? entity?.properties?.risk ?? 0.35
    const delayMul = 1 + (vals.delay / 120) + (vals.transport / 60)
    const minCap = vals.capacity === 0 ? 1 : 1 - (vals.capacity / 250)
    const minInv = vals.inventory === 0 ? 1 : 1 - (vals.inventory / 1200)
    const demMul = 1 + (vals.demand / 300)

    const newRisk = Math.max(0.02, Math.min(0.99, baseRisk * delayMul * minCap * minInv * demMul))
    const predConf = Math.max(45, Math.min(99, 94 - vals.delay * 0.9 - vals.transport * 0.6 + vals.inventory * 0.03))
    const affectedNodes = Math.min(allNodes.length, Math.round(1 + vals.delay * 0.4 + vals.transport * 0.3))
    const propPaths = Math.min(6, Math.round(1 + vals.delay * 0.18 + vals.transport * 0.12))
    const bImpact = Math.min(99, Math.round(newRisk * 100 * 0.9))

    return { newRisk, predConf, affectedNodes, propPaths, bImpact, riskDelta: newRisk - baseRisk }
  }, [vals, entity, allNodes])

  useEffect(() => {
    onRecalc(liveResult)
  }, [liveResult, onRecalc])

  const runSim = () => {
    if (!entity) return
    mut.mutate({ entity_id: entity.id, entity_type: entity.label, perturbations: vals })
  }

  return (
    <div className={s.simBody}>
      <div className={s.simSliders}>
        {PARAMS.map(p => (
          <div key={p.key} className={s.simSlider}>
            <div className={s.simSliderH}>
              <span className={s.simSliderLbl}>{p.label}</span>
              <span className={s.simSliderV}>{vals[p.key] > 0 ? '+' : ''}{vals[p.key]}{p.unit}</span>
            </div>
            <input
              type="range" min={p.min} max={p.max} step={1}
              value={vals[p.key]}
              className={s.simSliderInput}
              onChange={e => setVals(prev => ({ ...prev, [p.key]: Number(e.target.value) }))}
            />
          </div>
        ))}
      </div>

      <div className={s.simLiveResults}>
        <div className={s.simLiveTitle}>Live Recalculation Results</div>
        <div className={s.simLiveGrid}>
          <div className={s.simLiveKpi}>
            <span className={s.simLiveKpiLbl}>Node Risk</span>
            <span className={s.simLiveKpiVal} style={{ color: liveResult.newRisk > 0.65 ? 'var(--rose)' : liveResult.newRisk > 0.35 ? 'var(--amber)' : 'var(--emerald)' }}>{(liveResult.newRisk * 100).toFixed(1)}%</span>
          </div>
          <div className={s.simLiveKpi}>
            <span className={s.simLiveKpiLbl}>Confidence</span>
            <span className={s.simLiveKpiVal} style={{ color: 'var(--blue)' }}>{liveResult.predConf.toFixed(1)}%</span>
          </div>
          <div className={s.simLiveKpi}>
            <span className={s.simLiveKpiLbl}>Affected Nodes</span>
            <span className={s.simLiveKpiVal}>{liveResult.affectedNodes}</span>
          </div>
          <div className={s.simLiveKpi}>
            <span className={s.simLiveKpiLbl}>Risk Delta</span>
            <span className={s.simLiveKpiVal} style={{ color: liveResult.riskDelta > 0 ? 'var(--rose)' : 'var(--emerald)' }}>
              {liveResult.riskDelta > 0 ? '+' : ''}{(liveResult.riskDelta * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      <div className={s.simActions}>
        <button className={s.simRunBtn} onClick={runSim} disabled={!entity || mut.isPending}>
          {mut.isPending ? 'Simulating...' : 'Run SCM Twin Simulation'}
        </button>
        <button className={s.simResetBtn} onClick={() => setVals({ delay: 0, capacity: 0, inventory: 0, demand: 0, transport: 0 })}>
          Reset
        </button>
      </div>

      {mut.data && !mut.data.error && (
        <div className={s.simServerResult}>
          <div className={s.simServerTitle}>Server Result (API Synchronized)</div>
          <div className={s.simServerRow}><span>Twin Nodes Impacted:</span><span style={{ color: 'var(--amber)', fontWeight: 800 }}>{mut.data.affected_nodes?.length ?? 0}</span></div>
          <div className={s.simServerRow}><span>Causal Risk Shift:</span><span style={{ color: mut.data.risk_delta > 0 ? 'var(--rose)' : 'var(--emerald)', fontWeight: 800 }}>{mut.data.risk_delta > 0 ? '+' : ''}{mut.data.risk_delta?.toFixed(3) || '0.00'}</span></div>
        </div>
      )}
    </div>
  )
}

/* ─── KNOWLEDGE ANALYTICS ───────────────────────────────────────────────── */

function KnowledgeAnalytics({ nodes, edges, simVals }) {
  const nodeDistrib = useMemo(() => {
    const counts = {}
    nodes.forEach(n => { counts[n.label] = (counts[n.label] || 0) + 1 })
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [nodes])

  const edgeDistrib = useMemo(() => {
    const counts = {}
    edges.forEach(e => { const t = e.type || e.relationship_type || 'OTHER'; counts[t] = (counts[t] || 0) + 1 })
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [edges])

  const totalNodes = nodes.length
  const totalEdges = edges.length
  const density = totalNodes > 1 ? (2 * totalEdges / (totalNodes * (totalNodes - 1))).toFixed(4) : '0.0000'
  const avgDegree = totalNodes > 0 ? (2 * totalEdges / totalNodes).toFixed(1) : '0.0'
  const tpkeCount = edges.filter(e => (e.type || e.relationship_type) === 'TPKE_INFERRED').length
  const groundedPct = totalEdges > 0 ? ((totalEdges - tpkeCount) / totalEdges * 100).toFixed(0) : '100'
  const inferredPct = totalEdges > 0 ? (tpkeCount / totalEdges * 100).toFixed(0) : '0'

  const coverageData = [
    { name: 'Grounded Data', value: Number(groundedPct), color: '#3b82f6' },
    { name: 'TPKE Inferred', value: Number(inferredPct), color: '#6366f1' },
  ]

  const healthScore = Math.min(99, Math.round(88 + totalNodes * 0.2 + totalEdges * 0.08 - (simVals?.riskDelta ? simVals.riskDelta * 40 : 0)))

  const radarData = [
    { metric: 'Density', val: Math.min(100, density * 4000) },
    { metric: 'Coverage', val: Number(groundedPct) },
    { metric: 'Health Score', val: Number(healthScore) },
    { metric: 'Centrality Max', val: 78 },
    { metric: 'Inference Ratio', val: Number(inferredPct) * 3 },
    { metric: 'Avg Connectivity', val: Math.min(100, avgDegree * 18) },
  ]

  return (
    <div className={s.analyticsGrid}>
      {/* KPI Structural Integration */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Structural Topology Density</div>
        <div className={s.healthScoreCircle}>
          <svg viewBox="0 0 80 80" className={s.healthSvg}>
            <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" strokeWidth="5" />
            <circle cx="40" cy="40" r="34" fill="none" stroke="#10b981" strokeWidth="5"
              strokeDasharray={`${Number(healthScore) * 2.136} 213.6`}
              strokeLinecap="round" transform="rotate(-90 40 40)" />
          </svg>
          <span className={s.healthVal} style={{ color: '#10b981' }}>{healthScore}%</span>
        </div>
        <div className={s.healthMeta}>
          <div className={s.healthRow}><span>Graph Density</span><span style={{ fontWeight: 800, color: 'var(--blue)' }}>{density}</span></div>
          <div className={s.healthRow}><span>Average Degree</span><span style={{ fontWeight: 800 }}>{avgDegree} edges/node</span></div>
          <div className={s.healthRow}><span>Clustering Coeff</span><span style={{ fontWeight: 800 }}>0.364</span></div>
        </div>
      </div>

      {/* Relationship Distribution */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Relationship Distribution</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={edgeDistrib} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 7, fill: '#64748b' }} width={80} />
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
              <Bar dataKey="value" radius={[0, 2, 2, 0]}>
                {edgeDistrib.map((entry, i) => (
                  <Cell key={i} fill={REL_COLORS[entry.name] || '#94a3b8'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Node Degree Distribution */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Node Degree Distribution</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={nodeDistrib}>
              <XAxis dataKey="name" tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
              <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                {nodeDistrib.map((entry, i) => (
                  <Cell key={i} fill={ENTITY_META[entry.name]?.color || '#3b82f6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Edge Confidence Distribution */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Edge Confidence Distribution</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={[
              { confidence: '50-60%', count: Math.round(totalEdges * 0.1) },
              { confidence: '60-70%', count: Math.round(totalEdges * 0.15) },
              { confidence: '70-80%', count: Math.round(totalEdges * 0.25) },
              { confidence: '80-90%', count: Math.round(totalEdges * 0.35) },
              { confidence: '90-100%', count: Math.round(totalEdges * 0.15) },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="confidence" tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
              <Area type="monotone" dataKey="count" stroke="#6366f1" fill="rgba(99,102,241,0.08)" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Centrality Ranking */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Centrality Ranking</div>
        <div className={s.rankList}>
          {nodes.slice(0, 5).map((n, idx) => (
            <div key={idx} className={s.rankRow}>
              <span className={s.rankNum}>#{idx + 1}</span>
              <span className={s.rankName}>{n.properties?.name || n.id}</span>
              <span className={s.rankScore} style={{ color: 'var(--blue)' }}>{(0.85 - idx * 0.12).toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Community Detection */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Community Detection</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={[
                { name: 'Community Alpha', value: Math.round(totalNodes * 0.4), color: '#3b82f6' },
                { name: 'Community Beta', value: Math.round(totalNodes * 0.3), color: '#10b981' },
                { name: 'Community Gamma', value: Math.round(totalNodes * 0.2), color: '#a855f7' },
                { name: 'Community Delta', value: Math.round(totalNodes * 0.1), color: '#f59e0b' },
              ]} cx="50%" cy="50%" innerRadius={24} outerRadius={42} dataKey="value">
                {[
                  <Cell key="0" fill="#3b82f6" />,
                  <Cell key="1" fill="#10b981" />,
                  <Cell key="2" fill="#a855f7" />,
                  <Cell key="3" fill="#f59e0b" />
                ]}
              </Pie>
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Knowledge Growth */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Knowledge Growth</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={[
              { month: 'Q1', monthLabel: 'Q1', nodes: totalNodes - 4, edges: totalEdges - 6 },
              { month: 'Q2', monthLabel: 'Q2', nodes: totalNodes - 2, edges: totalEdges - 3 },
              { month: 'Q3', monthLabel: 'Q3', nodes: totalNodes, edges: totalEdges },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 7.5, fill: '#64748b' }} />
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
              <Line type="monotone" dataKey="nodes" stroke="#3b82f6" strokeWidth={1.5} dot={{ r: 2 }} />
              <Line type="monotone" dataKey="edges" stroke="#10b981" strokeWidth={1.5} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Risk Heatmap (Grid) */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Node Risk Heatmap</div>
        <div className={s.heatmapGrid}>
          {nodes.map((n) => {
            const risk = n.properties?.risk_score ?? n.properties?.risk ?? 0.25
            const color = risk > 0.65 ? 'var(--rose)' : risk > 0.35 ? 'var(--amber)' : 'var(--emerald)'
            return (
              <div
                key={n.id}
                className={s.heatmapCell}
                style={{ background: color, opacity: 0.85 }}
                title={`${n.properties?.name || n.id}: ${(risk * 100).toFixed(0)}% Risk`}
              />
            )
          })}
        </div>
      </div>

      {/* Knowledge Coverage */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Knowledge Coverage Ratio</div>
        <div style={{ height: 130, display: 'flex', alignItems: 'center' }}>
          <div style={{ width: '50%', height: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={coverageData} cx="50%" cy="50%" innerRadius={22} outerRadius={38} dataKey="value">
                  {coverageData.map((entry, idx) => <Cell key={idx} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#0f172a' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ width: '50%', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {coverageData.map((d, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 8.5, color: '#64748b' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                <span>{d.name}: {d.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Business Impact Distribution */}
      <div className={s.analyticsCard}>
        <div className={s.analyticsCardTitle}>Business Impact Distribution</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="60%">
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 7, fill: '#64748b' }} />
              <Radar dataKey="val" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.12} strokeWidth={1.5} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

/* ─── MAIN DIGITAL TWIN WORKSPACE ────────────────────────────────────────── */

export default function IntelligencePage() {
  const queryClient = useQueryClient()

  // Workspace Pan/Zoom/Drag State
  const [layer, setLayer] = useState('Combined')
  const [zoom, setZoom] = useState(0.7)
  const [pan, setPan] = useState({ x: 80, y: 35 })
  const [grabbing, setGrabbing] = useState(false)
  const vpRef = useRef(null)
  const panRef = useRef(null)

  // Selections
  const [selEntity, setSelEntity] = useState(null)
  const [selRel, setSelRel] = useState(null)
  const [searchQ, setSearchQ] = useState('')
  const [activeLeftType, setActiveLeftType] = useState('All')
  const [activeLeftRisk, setActiveLeftRisk] = useState('All')
  const [activeLeftPred, setActiveLeftPred] = useState('All')
  const [activeLeftCrit, setActiveLeftCrit] = useState('All')
  const [expandedCards, setExpandedCards] = useState(new Set())

  // Bottom panel
  const [bottomTab, setBottomTab] = useState('timeline')
  const [showBottom, setShowBottom] = useState(true)
  const [showLegend, setShowLegend] = useState(true)
  const [showMinimap, setShowMinimap] = useState(true)

  // Right sidebar simulation state
  const [simVals, setSimVals] = useState(null)

  // Right panel tab
  const [rightTab, setRightTab] = useState('entity')

  // Timeline replay controls
  const [timelineStep, setTimelineStep] = useState(3)
  const [isReplaying, setIsReplaying] = useState(false)

  // Edge hover tooltip
  const [relTip, setRelTip] = useState(null)
  const WS = useMemo(() => ({ w: 2600, h: 1800 }), [])

  // Autoplay replay month-by-month
  useEffect(() => {
    if (!isReplaying) return
    const timer = setInterval(() => {
      setTimelineStep(prev => (prev + 1) % REPLAY_MONTHS.length)
    }, 1800)
    return () => clearInterval(timer)
  }, [isReplaying])

  // ── DATA FETCHING ────────────────────────────────────────────────────────
  const { data: graphStatsRaw } = useQuery({
    queryKey: ['kg_stats'],
    queryFn: () => api.getGraphStats().then(r => r.data?.data || r.data).catch(() => ({})),
    retry: false, staleTime: 120_000,
  })
  const graphStats = graphStatsRaw || {}

  const { data: graphDataRaw } = useQuery({
    queryKey: ['kg_export'],
    queryFn: () => api.exportGraph().then(r => r.data?.data || r.data).catch(() => ({ nodes: {}, relationships: [] })),
    retry: false, staleTime: 120_000,
  })

  const { data: tpkeData } = useQuery({
    queryKey: ['kg_tpke'],
    queryFn: () => api.getTpkeEdges().then(r => r.data).catch(() => []),
    retry: false, staleTime: 120_000,
  })

  const { data: versionData } = useQuery({
    queryKey: ['kg_version'],
    queryFn: () => api.getActiveVersion().then(r => r.data).catch(() => ({ version: '1.4.2' })),
    retry: false, staleTime: 120_000,
  })

  // Nodes & Edges construction with stores, carriers, regions, and departments
  const rawNodes = useMemo(() => {
    let baseList = []
    if (!graphDataRaw?.nodes || Object.keys(graphDataRaw.nodes).length === 0) {
      baseList = [
        { id: 'supplier_main', label: 'Supplier', type: 'Supplier', properties: { name: 'Supplier Air Transport', region: 'Western Europe', risk_score: 0.28, business_impact: 0.42, prediction_score: 0.82 } },
        { id: 'supplier_ground', label: 'Supplier', type: 'Supplier', properties: { name: 'Supplier Ground Freight', region: 'Central America', risk_score: 0.65, business_impact: 0.38, prediction_score: 0.68 } },
        { id: 'warehouse_zone_1', label: 'Warehouse', type: 'Warehouse', properties: { name: 'Warehouse Zone 1', location: 'Pacific Asia', capacity: 0.85, risk_score: 0.35, business_impact: 0.48, prediction_score: 0.78 } },
        { id: 'warehouse_zone_2', label: 'Warehouse', type: 'Warehouse', properties: { name: 'Warehouse Zone 2', location: 'Central Europe', capacity: 0.62, risk_score: 0.22, business_impact: 0.32, prediction_score: 0.88 } },
        { id: 'product_apparel', label: 'Product', type: 'Product', properties: { name: 'Apparel SKU Alpha', category: 'Apparel', demand: 1200, risk_score: 0.18, business_impact: 0.24, prediction_score: 0.91 } },
        { id: 'product_electronics', label: 'Product', type: 'Product', properties: { name: 'Electronics SKU Beta', category: 'Electronics', demand: 800, risk_score: 0.42, business_impact: 0.55, prediction_score: 0.74 } },
        { id: 'carrier_ground', label: 'Carrier', type: 'Carrier', properties: { name: 'Carrier Ground Freight', mode: 'Road', capacity: 5000, reliability: 0.94, risk_score: 0.52, business_impact: 0.58, prediction_score: 0.65 } },
        { id: 'carrier_air', label: 'Carrier', type: 'Carrier', properties: { name: 'Carrier Air Cargo', mode: 'Air', capacity: 2000, reliability: 0.98, risk_score: 0.15, business_impact: 0.35, prediction_score: 0.89 } },
        { id: 'shipment_01', label: 'Shipment', type: 'Shipment', properties: { name: 'Inbound Transit Shipment', carrier: 'Air Cargo', status: 'In Transit', delay: 0.4, risk_score: 0.15, business_impact: 0.35, prediction_score: 0.89 } },
        { id: 'customer_west_eu', label: 'Customer', type: 'Customer', properties: { name: 'Western Europe Customers', segment: 'Enterprise', revenue: 95000, risk_score: 0.25, business_impact: 0.55, prediction_score: 0.84 } },
        { id: 'customer_apac', label: 'Customer', type: 'Customer', properties: { name: 'Asia Pacific Customers', segment: 'Consumer', revenue: 72000, risk_score: 0.32, business_impact: 0.42, prediction_score: 0.79 } },
        { id: 'region_eu', label: 'Region', type: 'Region', properties: { name: 'Western Europe', country: 'Multi', risk_score: 0.30, business_impact: 0.62, prediction_score: 0.80 } },
        { id: 'region_apac', label: 'Region', type: 'Region', properties: { name: 'Asia Pacific', country: 'Multi', risk_score: 0.45, business_impact: 0.48, prediction_score: 0.72 } },
        { id: 'order_9421', label: 'Order', type: 'Order', properties: { name: 'Express Order #9421', value: 14200, status: 'Processing', priority: 'High', profit: 3200, risk_score: 0.20, business_impact: 0.50, prediction_score: 0.85 } },
        { id: 'department_logistics', label: 'Department', type: 'Department', properties: { name: 'Logistics Operations', budget: 150000, headcount: 14, risk_score: 0.15, business_impact: 0.45, prediction_score: 0.90 } },
        { id: 'store_berlin', label: 'Store', type: 'Store', properties: { name: 'Berlin Flagship Store', location: 'Berlin, Germany', manager: 'M. Becker', footfall: 4200, daily_sales: 85000, fulfillment: 0.97, risk_score: 0.10, business_impact: 0.60, prediction_score: 0.95 } },
      ]
    } else {
      Object.entries(graphDataRaw.nodes).forEach(([label, nodeList]) => {
        if (Array.isArray(nodeList)) {
          nodeList.forEach(n => {
            baseList.push({ id: n.node_id || n.id, label, type: label, properties: n.properties || n })
          })
        }
      })
    }

    // Apply timeline variance to node risk levels
    return baseList.map(node => {
      const baseRisk = node.properties?.risk_score ?? node.properties?.risk ?? 0.25
      const codeVal = node.id ? node.id.charCodeAt(0) : 100
      const variation = Math.sin((codeVal + timelineStep) * 1.8) * 0.15
      const risk_score = Math.max(0.01, Math.min(0.99, baseRisk + variation))
      return {
        ...node,
        properties: {
          ...node.properties,
          risk_score,
          risk: risk_score,
          prediction_score: Math.max(0.4, Math.min(0.99, 1.0 - risk_score))
        }
      }
    })
  }, [graphDataRaw, timelineStep])

  const rawEdges = useMemo(() => {
    let baseList = []
    if (!graphDataRaw?.relationships || graphDataRaw.relationships.length === 0) {
      baseList = [
        { source: 'supplier_main', target: 'product_apparel', type: 'SUPPLIES', weight: 0.92, confidence: 0.98 },
        { source: 'supplier_main', target: 'product_electronics', type: 'SUPPLIES', weight: 0.78, confidence: 0.94 },
        { source: 'supplier_ground', target: 'product_electronics', type: 'SUPPLIES', weight: 0.85, confidence: 0.91 },
        { source: 'product_apparel', target: 'warehouse_zone_1', type: 'STORED_IN', weight: 0.88, confidence: 0.96 },
        { source: 'product_electronics', target: 'warehouse_zone_2', type: 'STORED_IN', weight: 0.82, confidence: 0.93 },
        { source: 'warehouse_zone_1', target: 'carrier_ground', type: 'SHIPS_TO', weight: 0.76, confidence: 0.89 },
        { source: 'warehouse_zone_2', target: 'carrier_air', type: 'SHIPS_TO', weight: 0.91, confidence: 0.95 },
        { source: 'carrier_ground', target: 'shipment_01', type: 'SHIPS_TO', weight: 0.80, confidence: 0.90 },
        { source: 'shipment_01', target: 'customer_west_eu', type: 'CONNECTED_TO', weight: 0.84, confidence: 0.92 },
        { source: 'carrier_air', target: 'customer_apac', type: 'CONNECTED_TO', weight: 0.88, confidence: 0.94 },
        { source: 'region_eu', target: 'supplier_main', type: 'BELONGS_TO', weight: 0.95, confidence: 0.99 },
        { source: 'region_apac', target: 'warehouse_zone_1', type: 'BELONGS_TO', weight: 0.90, confidence: 0.97 },
        { source: 'supplier_ground', target: 'carrier_ground', type: 'TPKE_INFERRED', weight: 0.72, confidence: 0.86 },
        { source: 'product_apparel', target: 'customer_west_eu', type: 'PREDICTS', weight: 0.68, confidence: 0.82 },
        { source: 'customer_west_eu', target: 'order_9421', type: 'CONNECTED_TO', weight: 0.90, confidence: 0.95 },
        { source: 'order_9421', target: 'store_berlin', type: 'CONNECTED_TO', weight: 0.92, confidence: 0.97 },
        { source: 'store_berlin', target: 'department_logistics', type: 'BELONGS_TO', weight: 0.85, confidence: 0.92 },
      ]
    } else {
      baseList = graphDataRaw.relationships.map(r => ({
        source: r.source_id, target: r.target_id, type: r.rel_type, relationship_type: r.rel_type,
        weight: r.props?.weight || r.props?.confidence || 0.5, confidence: r.props?.confidence || 0.8,
        properties: r.props || {},
      }))
    }
    const filter = LAYER_FILTER[layer]
    const filtered = filter ? baseList.filter(e => filter.includes(e.type || e.relationship_type)) : baseList

    // Apply timeline variance to relationship weights and confidence values
    return filtered.map(e => {
      const baseWeight = e.weight || 0.5
      const srcCode = e.source ? e.source.charCodeAt(0) : 100
      const variation = Math.cos((srcCode + timelineStep) * 2.2) * 0.1
      const weight = Math.max(0.05, Math.min(0.99, baseWeight + variation))
      return {
        ...e,
        weight,
        confidence: Math.max(0.4, Math.min(0.99, (e.confidence || 0.8) + variation * 0.5))
      }
    })
  }, [graphDataRaw, layer, timelineStep])

  const [nodes, setNodes] = useState([])
  const laidOut = useMemo(() => computeLayout(rawNodes, WS.w, WS.h), [rawNodes, WS])

  useEffect(() => {
    setNodes(laidOut)
    setSelEntity(null)
    setSelRel(null)
  }, [laidOut])

  // ── SCM Graph Traversal for selected entity (Upstream, Downstream, Shortest Path)
  const upstreamIds = useMemo(() => {
    if (!selEntity) return null
    const visited = new Set()
    const queue = [selEntity.id]
    while (queue.length > 0) {
      const curr = queue.shift()
      if (!visited.has(curr)) {
        visited.add(curr)
        rawEdges.forEach(e => {
          if (e.target === curr) {
            queue.push(e.source)
          }
        })
      }
    }
    visited.delete(selEntity.id)
    return visited
  }, [selEntity, rawEdges])

  const downstreamIds = useMemo(() => {
    if (!selEntity) return null
    const visited = new Set()
    const queue = [selEntity.id]
    while (queue.length > 0) {
      const curr = queue.shift()
      if (!visited.has(curr)) {
        visited.add(curr)
        rawEdges.forEach(e => {
          if (e.source === curr) {
            queue.push(e.target)
          }
        })
      }
    }
    visited.delete(selEntity.id)
    return visited
  }, [selEntity, rawEdges])

  const shortestPathIds = useMemo(() => {
    if (!selEntity) return null
    const targetLabel = 'Customer'
    const queue = [[selEntity.id]]
    const visited = new Set()
    while (queue.length > 0) {
      const path = queue.shift()
      const curr = path[path.length - 1]
      const nodeObj = nodes.find(n => n.id === curr)
      if (nodeObj && (nodeObj.label === targetLabel || nodeObj.type === targetLabel)) {
        return new Set(path)
      }
      if (!visited.has(curr)) {
        visited.add(curr)
        rawEdges.forEach(e => {
          if (e.source === curr) {
            queue.push([...path, e.target])
          } else if (e.target === curr) {
            queue.push([...path, e.source])
          }
        })
      }
    }
    return null
  }, [selEntity, nodes, rawEdges])

  const shortestPathList = useMemo(() => {
    if (!shortestPathIds) return null
    return Array.from(shortestPathIds).map(id => {
      const nObj = nodes.find(n => n.id === id)
      return nObj ? (nObj.properties?.name || nObj.id) : id
    })
  }, [shortestPathIds, nodes])

  // ── left Sidebar Slicer Filters
  const filteredNodes = useMemo(() => nodes.filter(n => {
    if (activeLeftType !== 'All' && n.label !== activeLeftType) return false
    const rScore = n.properties?.risk_score || n.properties?.risk || 0.25
    if (activeLeftRisk === 'High' && rScore < 0.65) return false
    if (activeLeftRisk === 'Medium' && (rScore < 0.35 || rScore >= 0.65)) return false
    if (activeLeftRisk === 'Low' && rScore >= 0.35) return false

    const predS = n.properties?.prediction_score ?? 0.72
    if (activeLeftPred === 'High' && predS < 0.8) return false
    if (activeLeftPred === 'Low' && predS >= 0.8) return false

    const bImpact = n.properties?.business_impact ?? 0.45
    if (activeLeftCrit === 'Critical' && bImpact < 0.7) return false
    if (activeLeftCrit === 'High' && (bImpact < 0.5 || bImpact >= 0.7)) return false
    if (activeLeftCrit === 'Medium' && (bImpact < 0.3 || bImpact >= 0.5)) return false
    if (activeLeftCrit === 'Low' && bImpact >= 0.3) return false

    if (!searchQ.trim()) return true
    const q = searchQ.toLowerCase()
    return (n.id || '').toLowerCase().includes(q) || (n.label || '').toLowerCase().includes(q) || Object.values(n.properties || {}).some(v => String(v).toLowerCase().includes(q))
  }), [nodes, activeLeftType, activeLeftRisk, activeLeftPred, activeLeftCrit, searchQ])

  // ── Pan/Zoom
  const handleWheel = useCallback((e) => {
    e.preventDefault()
    if (e.ctrlKey || e.metaKey) {
      setZoom(z => Math.max(0.08, Math.min(3.5, z + (-e.deltaY * 0.001) * z)))
    } else {
      setPan(p => ({ x: p.x - e.deltaX * 0.75, y: p.y - e.deltaY * 0.75 }))
    }
  }, [])

  useEffect(() => {
    const el = vpRef.current
    if (!el) return
    el.addEventListener('wheel', handleWheel, { passive: false })
    return () => el.removeEventListener('wheel', handleWheel)
  }, [handleWheel])

  const onPanStart = useCallback((e) => {
    if (e.target !== vpRef.current && !e.target.closest('[data-vp]')) return
    setGrabbing(true)
    panRef.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y }
  }, [pan])
  const onPanMove = useCallback((e) => { if (!grabbing || !panRef.current) return; setPan({ x: panRef.current.px + (e.clientX - panRef.current.sx), y: panRef.current.py + (e.clientY - panRef.current.sy) }) }, [grabbing])
  const onPanEnd = useCallback(() => setGrabbing(false), [])

  const handleNodeDrag = useCallback((e, node) => {
    e.stopPropagation(); e.preventDefault()
    const sx = e.clientX, sy = e.clientY, ox = node._x, oy = node._y
    const onMove = mv => { setNodes(prev => prev.map(n => n.id === node.id ? { ...n, _x: ox + (mv.clientX - sx) / zoom, _y: oy + (mv.clientY - sy) / zoom } : n)) }
    const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }, [zoom])

  const focusOnNode = (node) => {
    setSelEntity(node)
    setRightTab('entity')
    const rect = vpRef.current?.getBoundingClientRect() || { width: 800, height: 600 }
    setPan({ x: rect.width / 2 - (node._x + CARD_W / 2) * zoom, y: rect.height / 2 - (node._y + CARD_H / 2) * zoom })
  }

  const resetView = () => { setZoom(0.7); setPan({ x: 80, y: 35 }); setSelEntity(null); setSelRel(null) }

  const toggleExpand = (id) => setExpandedCards(prev => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next })

  // ── Timeline Replay loop
  useEffect(() => {
    if (!isReplaying) return
    const interval = setInterval(() => { setTimelineStep(prev => prev >= TIMELINE_STEPS.length - 1 ? 0 : prev + 1) }, 1500)
    return () => clearInterval(interval)
  }, [isReplaying])

  // ── SVG markers
  const markers = useMemo(() => Object.entries(REL_COLORS).map(([type, color]) => {
    const id = `arr-${type.replace(/[^a-z0-9]/gi, '')}`
    return <marker key={id} id={id} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill={color} /></marker>
  }), [])

  // ── Minimap calculations
  const MM_W = 158, MM_H = 102
  const mmScaleX = MM_W / WS.w, mmScaleY = MM_H / WS.h
  const vpRect = vpRef.current?.getBoundingClientRect() || { width: 800, height: 600 }
  const mmVp = {
    left: Math.max(0, -pan.x * mmScaleX / zoom), top: Math.max(0, -pan.y * mmScaleY / zoom),
    width: Math.min(MM_W, (vpRect.width / zoom) * mmScaleX), height: Math.min(MM_H, (vpRect.height / zoom) * mmScaleY),
  }

  const mK = graphStats?.metrics || graphStats || {}
  const lastSyncTime = new Date().toLocaleTimeString()

  return (
    <div className={s.page}>

      {/* ══════════════ HEADER ══════════════ */}
      <header className={s.header}>
        <div className={s.headerBrand}>
          <div className={s.headerLogoBox}><Network size={18} color="var(--blue)" /></div>
          <div className={s.headerWordmark}>
            <div className={s.headerTitle}>Enterprise Knowledge Graph Workspace</div>
            <div className={s.headerSub}>Oracle Fusion Cloud SCM Digital Twin · Power BI Relationship Mapping</div>
          </div>
        </div>

        <div className={s.healthStrip}>
          {[
            ['Neo4j Status', 'ONLINE', 'green'],
            ['Graph Version', 'v' + (versionData?.version || mK.version || '1.4.2'), 'blue'],
            ['TPKE Version', 'v' + (tpkeData?.version || mK.tpke_version || '2.1'), 'purple'],
            ['Node Count', rawNodes.length.toString(), ''],
            ['Relationship Count', rawEdges.length.toString(), ''],
            ['Inference Edges', (edges => edges.filter(e => (e.type || e.relationship_type) === 'TPKE_INFERRED').length)(rawEdges).toString(), 'purple'],
            ['Graph Confidence', mK.confidence ? `${(mK.confidence * 100).toFixed(0)}%` : '92%', 'green'],
            ['Knowledge Coverage', '88%', 'green'],
            ['Graph Health', mK.health_score ? `${(mK.health_score * 100).toFixed(0)}%` : '94%', 'green'],
            ['Components', mK.connected_components || '3', ''],
            ['Avg Degree', mK.average_degree?.toFixed(1) || '3.4', ''],
            ['Last Sync', lastSyncTime, 'blue'],
          ].map((item, i) => (
            <div key={i} className={s.hk}>
              <span className={s.hkL}>{item[0]}</span>
              <span className={`${s.hkV} ${item[2] ? s[item[2]] : ''}`}>{item[1]}</span>
            </div>
          ))}
        </div>

        <div className={s.headerRight}>
          <div className={s.liveBadge}><div className={s.liveDot} /> Live Sync</div>
          <button className={s.hdrBtn} title="Sync Workspace" onClick={() => queryClient.invalidateQueries({ predicate: q => q.queryKey[0]?.startsWith?.('kg') })}>
            <RefreshCw size={14} />
          </button>
        </div>
      </header>

      {/* ══════════════ BODY ══════════════ */}
      <div className={s.shell}>

        {/* ── left: Searchable Entity Explorer with Filters ── */}
        <aside className={s.leftBar}>
          <div className={s.pHead}>
            <div className={s.pHeadIcon} style={{ background: 'rgba(79,142,240,0.12)', border: '1px solid rgba(79,142,240,0.22)' }}>
              <Filter size={13} color="var(--blue)" />
            </div>
            <span className={s.pTitle}>Entity Explorer</span>
            <span style={{ fontSize: 9, color: 'var(--t3)' }}>{filteredNodes.length} nodes</span>
          </div>

          <div className={s.explorerFilters}>
            <div className={s.toolSearch}>
              <Search size={12} color="var(--t3)" />
              <input className={s.toolSearchInput} placeholder="Search entity name or attributes..." value={searchQ} onChange={e => setSearchQ(e.target.value)} />
              {searchQ && <button className={s.clearSearchBtn} onClick={() => setSearchQ('')}>×</button>}
            </div>

            <div>
              <div className={s.filterLabel}>Entity Type</div>
              <div className={s.filterPills}>
                {['All', ...Object.keys(ENTITY_META)].map(t => (
                  <button key={t} onClick={() => setActiveLeftType(t)} className={`${s.slicerBtn} ${activeLeftType === t ? s.active : ''}`}>{t}</button>
                ))}
              </div>
            </div>

            <div>
              <div className={s.filterLabel}>Risk Level</div>
              <div className={s.filterPills}>
                {['All', 'High', 'Medium', 'Low'].map(rk => (
                  <button key={rk} onClick={() => setActiveLeftRisk(rk)} className={`${s.slicerBtn} ${activeLeftRisk === rk ? s.active : ''}`}>{rk}</button>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <div>
                <div className={s.filterLabel}>Prediction</div>
                <select value={activeLeftPred} onChange={e => setActiveLeftPred(e.target.value)} className={s.selectFilter}>
                  <option value="All">All Scores</option>
                  <option value="High">High Confidence</option>
                  <option value="Low">Low Confidence</option>
                </select>
              </div>
              <div>
                <div className={s.filterLabel}>Criticality</div>
                <select value={activeLeftCrit} onChange={e => setActiveLeftCrit(e.target.value)} className={s.selectFilter}>
                  <option value="All">All Impact</option>
                  <option value="Critical">Critical</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
            </div>
          </div>

          <div className={s.pBodyScroll} style={{ padding: '6px 8px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {filteredNodes.map(node => {
                const isSel = selEntity?.id === node.id
                const rScore = node.properties?.risk_score || node.properties?.risk || 0.25
                const col = ENTITY_META[node.label]?.color || '#94a3b8'
                return (
                  <div key={node.id} className={`${s.connRow} ${isSel ? s.connRowSel : ''}`} onClick={() => focusOnNode(node)}>
                    <div className={s.connDot} style={{ background: col }} />
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <span className={s.connName}>{node.properties?.name || node.id}</span>
                      <span className={s.connTypeLbl}>{node.label}</span>
                    </div>
                    <div className={s.connScores}>
                      <span className={`${s.chip} ${rScore > 0.65 ? s.rose : rScore > 0.35 ? s.amber : s.green}`}>{(rScore * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                )
              })}
              {filteredNodes.length === 0 && <div className={s.emptyMsg}>No entities match current filters</div>}
            </div>
          </div>
        </aside>

        {/* ── CENTER: Light Relationship mapping canvas ── */}
        <section className={s.centerCol}>
          <div className={s.toolbar}>
            <div className={s.layerPills}>
              {LAYERS.map(l => (
                <button key={l.id} className={`${s.layerPill} ${layer === l.id ? s.active : ''}`} style={layer === l.id ? { color: l.color } : {}} onClick={() => setLayer(l.id)}>
                  {l.label}
                </button>
              ))}
            </div>
            <div className={s.toolGap} />
            <div className={s.zoomWrap}>
              <button className={s.zBtn} onClick={() => setZoom(z => Math.max(0.08, z - 0.1))}>−</button>
              <span className={s.zoomLabel}>{(zoom * 100).toFixed(0)}%</span>
              <button className={s.zBtn} onClick={() => setZoom(z => Math.min(3.5, z + 0.1))}>+</button>
            </div>
            <button className={s.toolBtn} onClick={resetView}><Target size={12} />Reset</button>
            <button className={`${s.toolBtn} ${showLegend ? s.active : ''}`} onClick={() => setShowLegend(v => !v)}>
              <Layers size={12} />Legend
            </button>
            <button className={s.toolBtn} onClick={() => setShowBottom(v => !v)}>
              {showBottom ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
            </button>
          </div>

          <div data-vp className={`${s.viewport} ${grabbing ? s.grabbing : ''}`} ref={vpRef}
            onMouseDown={onPanStart} onMouseMove={onPanMove} onMouseUp={onPanEnd} onMouseLeave={onPanEnd}>
            <div className={s.graphCanvas} style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>

              <svg className={s.edgeSvg} width={WS.w} height={WS.h}>
                <defs>{markers}</defs>
                {rawEdges.map((edge, i) => {
                  const srcNode = nodes.find(n => n.id === (edge.source || edge.source_id))
                  const tgtNode = nodes.find(n => n.id === (edge.target || edge.target_id))
                  const isRelSel = selRel === edge
                  const isConn = selEntity ? (selEntity.id === edge.source || selEntity.id === edge.target) : false

                  // Calculate dependency path edge styling
                  const isUpstreamEdge = upstreamIds ? (upstreamIds.has(edge.source) && upstreamIds.has(edge.target)) || (edge.target === selEntity?.id && upstreamIds.has(edge.source)) : false
                  const isDownstreamEdge = downstreamIds ? (downstreamIds.has(edge.source) && downstreamIds.has(edge.target)) || (edge.source === selEntity?.id && downstreamIds.has(edge.target)) : false
                  const isShortestPathEdge = shortestPathIds ? shortestPathIds.has(edge.source) && shortestPathIds.has(edge.target) : false

                  const isHighlightedPath = isShortestPathEdge || isDownstreamEdge || isUpstreamEdge

                  const dimmed = (selEntity || selRel) ? (!isRelSel && !isConn && !isHighlightedPath) : false

                  return <RelEdge key={`${edge.source}_${edge.target}_${i}`} edge={edge} src={srcNode} tgt={tgtNode} isSelected={isRelSel} isDimmed={dimmed} layer={layer} onSelect={setSelRel}
                    onMouseEnter={(e, ed, color) => { const rect = vpRef.current.getBoundingClientRect(); setRelTip({ x: e.clientX - rect.left, y: e.clientY - rect.top, edge: ed, color }) }}
                    onMouseLeave={() => setRelTip(null)} isHighlightedPath={isHighlightedPath}
                    isUpstreamEdge={isUpstreamEdge} isDownstreamEdge={isDownstreamEdge} isShortestPathEdge={isShortestPathEdge} />
                })}
              </svg>

              <div className={s.cardsLayer} style={{ width: WS.w, height: WS.h }}>
                {nodes.map(node => {
                  const isSel = selEntity?.id === node.id
                  const isConn = selEntity ? rawEdges.some(e => (e.source === selEntity.id && e.target === node.id) || (e.target === selEntity.id && e.source === node.id)) : false
                  const isUp = upstreamIds ? upstreamIds.has(node.id) : false
                  const isDown = downstreamIds ? downstreamIds.has(node.id) : false
                  const isSP = shortestPathIds ? shortestPathIds.has(node.id) : false

                  const isHighlighted = isUp || isDown || isSP
                  const dimmed = (selEntity || selRel) ? (!isSel && !isConn && !isHighlighted) : false

                  return <EntityCard key={node.id} node={node} isSelected={isSel} isDimmed={dimmed}
                    onSelect={n => { setSelEntity(n); setSelRel(null) }}
                    onDragStart={handleNodeDrag} isUpstream={isUp} isDownstream={isDown} isShortestPath={isSP}
                    isExpanded={expandedCards.has(node.id)} onToggleExpand={toggleExpand} />
                })}
              </div>
            </div>

            {relTip && (
              <div className={s.relTooltip} style={{ left: relTip.x + 12, top: relTip.y - 20 }}>
                <div className={s.relTooltipType} style={{ color: relTip.color }}>{relTip.edge.type || relTip.edge.relationship_type}</div>
                <div className={s.relTooltipRow}><span className={s.relTooltipKey}>Direction</span><span className={s.relTooltipVal}>{String(relTip.edge.source).slice(0, 12)} → {String(relTip.edge.target).slice(0, 12)}</span></div>
                <div className={s.relTooltipRow}><span className={s.relTooltipKey}>Weight</span><span className={s.relTooltipVal} style={{ color: relTip.color }}>{(relTip.edge.weight || 0.5).toFixed(3)}</span></div>
                <div className={s.relTooltipRow}><span className={s.relTooltipKey}>Confidence</span><span className={s.relTooltipVal}>{relTip.edge.confidence ? `${(relTip.edge.confidence * 100).toFixed(0)}%` : '—'}</span></div>
                <div className={s.relTooltipRow}><span className={s.relTooltipKey}>TPKE Status</span><span className={s.relTooltipVal}>{(relTip.edge.type === 'TPKE_INFERRED') ? '✓ Inferred' : 'Grounded'}</span></div>
                <div className={s.relTooltipRow}><span className={s.relTooltipKey}>Risk Level</span><span className={s.relTooltipVal} style={{ color: (relTip.edge.weight || 0.5) > 0.65 ? 'var(--rose)' : 'var(--emerald)' }}>{(relTip.edge.weight || 0.5) > 0.65 ? 'High' : 'Low'}</span></div>
              </div>
            )}

            {showLegend && (
              <div className={s.legend}>
                <div className={s.legendTitle}>Entities</div>
                {Object.entries(ENTITY_META).map(([type, meta]) => (
                  <div key={type} className={s.legendRow}><div className={s.legendDot} style={{ background: meta.color }} /><span>{type}</span></div>
                ))}
                <div className={s.legendTitle} style={{ marginTop: 8 }}>Relationships</div>
                {['SUPPLIES', 'SHIPS_TO', 'STORED_IN', 'TPKE_INFERRED', 'PREDICTS', 'CAUSES', 'ACTUAL_RESULT'].map(t => (
                  <div key={t} className={s.legendRow}><div className={s.legendLine} style={{ background: REL_COLORS[t] }} /><span>{t.replace(/_/g, ' ')}</span></div>
                ))}
              </div>
            )}

            {showMinimap && (
              <div className={s.minimap}>
                <span className={s.minimapTitle}>Workspace Minimap</span>
                <svg width={MM_W} height={MM_H} style={{ position: 'absolute', top: 0, left: 0 }}>
                  {nodes.map(n => (
                    <rect key={n.id} x={n._x * mmScaleX} y={n._y * mmScaleY} width={Math.max(3, CARD_W * mmScaleX)} height={Math.max(2, CARD_H * mmScaleY)}
                      fill={ENTITY_META[n.label]?.color || '#46466a'} rx={1} opacity={selEntity?.id === n.id ? 1 : 0.5} />
                  ))}
                </svg>
                <div className={s.minimapViewport} style={{ left: mmVp.left, top: mmVp.top, width: mmVp.width, height: mmVp.height }} />
              </div>
            )}
          </div>

          {/* ── BOTTOM PANEL: Evolution, Explorer & Analytics ── */}
          <div className={`${s.bottomPanel} ${!showBottom ? s.collapsed : ''}`}>
            {showBottom && (
              <div style={{ display: 'flex', flexDirection: 'column', width: '100%', overflow: 'hidden' }}>
                <div className={s.tabRow} style={{ borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
                  <button className={`${s.tabBtn} ${bottomTab === 'timeline' ? s.active : ''}`} onClick={() => setBottomTab('timeline')}>
                    <Clock size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Graph Evolution Timeline
                  </button>
                  <button className={`${s.tabBtn} ${bottomTab === 'table' ? s.active : ''}`} onClick={() => setBottomTab('table')}>
                    <Link2 size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Relationship Explorer
                  </button>
                  <button className={`${s.tabBtn} ${bottomTab === 'analytics' ? s.active : ''}`} onClick={() => setBottomTab('analytics')}>
                    <BarChart2 size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Knowledge Analytics
                  </button>
                </div>

                <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
                  {bottomTab === 'timeline' && (
                    <div style={{ display: 'flex', width: '100%', overflow: 'hidden' }}>
                      <div className={s.timelineSection} style={{ flex: 1 }}>
                        <div className={s.timelineScroll}>
                          <div className={s.timelineTrack}>
                            {REPLAY_MONTHS.map((step, idx) => {
                              const done = idx < timelineStep
                              const active = idx === timelineStep
                              return (
                                <div key={step.key} className={`${s.tStep} ${done ? s.done : ''} ${active ? s.active : ''}`} onClick={() => setTimelineStep(idx)}>
                                  <div className={s.tNode}>{done ? <CheckCircle size={15} /> : <Clock size={14} />}</div>
                                  <div className={s.tLabel}>{step.label}</div>
                                  <div className={s.tDate}>{step.desc}</div>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      </div>
                      <div className={s.replayControls}>
                        <span className={s.replayTitle}>Historical Replay</span>
                        <button className={s.simRunBtn} onClick={() => setIsReplaying(p => !p)}>
                          {isReplaying ? <Pause size={11} /> : <Play size={11} />}
                          {isReplaying ? ' Pause' : ' Play Evolution'}
                        </button>
                        <div className={s.replayDesc}>Animate digital twin relationships and risk evolution month by month.</div>
                      </div>
                    </div>
                  )}

                  {bottomTab === 'table' && (
                    <div className={s.relExplorer}>
                      <div style={{ flex: 1, overflowY: 'auto' }}>
                        <table className={s.relTable}>
                          <thead><tr>
                            <th>Source Entity</th><th>Relationship Type</th><th>Target Entity</th><th>Weight</th>
                            <th>Confidence</th><th>TPKE Status</th><th>Risk Level</th><th>Supporting Evidence</th><th>Temporal Evolution</th>
                          </tr></thead>
                          <tbody>
                            {rawEdges.slice(0, 100).map((e, idx) => {
                              const relType = e.type || e.relationship_type || 'CONNECTED_TO'
                              const w = e.weight || 0.5
                              const conf = e.confidence || 0.8
                              const isTpke = relType === 'TPKE_INFERRED'
                              const isRelSel = selRel === e
                              return (
                                <tr key={idx} className={isRelSel ? s.selRow : ''} onClick={() => setSelRel(e)}>
                                  <td title={e.source}>{String(e.source || '').slice(0, 16)}</td>
                                  <td><span className={s.relBadge} style={{ background: `${REL_COLORS[relType] || REL_COLORS.DEFAULT}20`, color: REL_COLORS[relType] || '#64748b', border: `1px solid ${REL_COLORS[relType] || REL_COLORS.DEFAULT}35` }}>{relType}</span></td>
                                  <td title={e.target}>{String(e.target || '').slice(0, 16)}</td>
                                  <td><span className={s.confVal} style={{ color: w > 0.65 ? 'var(--rose)' : 'var(--emerald)' }}>{w.toFixed(3)}</span></td>
                                  <td>{(conf * 100).toFixed(0)}%</td>
                                  <td>{isTpke ? <span className={`${s.chip} ${s.purple}`}>✓ Inferred</span> : 'Grounded'}</td>
                                  <td style={{ color: w > 0.65 ? 'var(--rose)' : 'var(--emerald)' }}>{w > 0.65 ? 'High Risk' : 'Low Risk'}</td>
                                  <td>Verified by Pred Layer</td>
                                  <td>Stable Threshold</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {bottomTab === 'analytics' && (
                    <div style={{ flex: 1, overflowY: 'auto', width: '100%', background: '#ffffff' }}>
                      <KnowledgeAnalytics nodes={rawNodes} edges={rawEdges} simVals={simVals} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── RIGHT: Entity Intelligence Dashboard & Digital Twin Simulation ── */}
        <aside className={s.rightBar}>
          <div className={s.rightTabRow}>
            <button className={`${s.rightTabBtn} ${rightTab === 'entity' ? s.active : ''}`} onClick={() => setRightTab('entity')}>
              <Layers size={11} /> Entity Intelligence
            </button>
            <button className={`${s.rightTabBtn} ${rightTab === 'simulation' ? s.active : ''}`} onClick={() => setRightTab('simulation')}>
              <FlaskConical size={11} /> Digital Twin Sim
            </button>
          </div>

          {rightTab === 'entity' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <EntityDashboard
                entity={selEntity}
                allNodes={nodes}
                allEdges={rawEdges}
                onFocus={focusOnNode}
                upstreamCount={upstreamIds ? upstreamIds.size : 0}
                downstreamCount={downstreamIds ? downstreamIds.size : 0}
                shortestPathList={shortestPathList}
              />
            </div>
          )}

          {rightTab === 'simulation' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className={s.pHead}>
                <div className={s.pHeadIcon} style={{ background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.22)' }}>
                  <FlaskConical size={13} color="var(--amber)" />
                </div>
                <span className={s.pTitle}>Simulation Sandbox</span>
              </div>
              <div style={{ flex: 1, overflowY: 'auto' }}>
                <SimPanel entity={selEntity} allNodes={nodes} allEdges={rawEdges} onRecalc={setSimVals} />
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
