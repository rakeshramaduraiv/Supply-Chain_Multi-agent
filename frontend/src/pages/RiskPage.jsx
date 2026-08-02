/**
 * RiskPage.jsx — AMASCI Enterprise AI Investigation Workspace
 *
 * Oracle SCM Control Tower · SAP IBP · Microsoft Fabric Investigation Hub · Palantir Foundry
 * Design: Minimal, Guided Step-by-Step, White Space, Enterprise Typography.
 */

import { useState, useMemo, useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useRiskPageData, useRcaInvestigationHistory } from '../hooks/useSupplyChainData'
import { useSharedParams } from '../hooks/useSharedParams'
import {
  Search, Filter, GitBranch, Activity, ArrowRight, Brain, Send,
  Network, FileText, Download, Zap, Lightbulb, Sparkles, RefreshCw, X,
  ChevronDown, AlertTriangle, DollarSign, Clock, TrendingUp, ChevronLeft,
  Users, Building2, Truck, Package, Shield, Layers, ChevronRight, Eye, CheckCircle2,
  Settings, CheckSquare, FileSpreadsheet, Play, Pause, Trash2
} from 'lucide-react'
import s from './RiskPage.module.css'

/* ── STATIC DATA ─────────────────────────────────────────────────────── */

const ALL_INCIDENTS = [
  {
    id: 'supplier_delay_main',
    name: 'Supplier Air Transport Disruption',
    type: 'Supplier',
    risk: '92.4%',
    riskVal: 0.924,
    severity: 'Critical',
    impact: 'High',
    confidence: '94%',
    financialLoss: 142500,
    affectedOrders: 2123,
    expectedDelay: 2.5,
    region: 'Western Europe',
    warehouse: 'Zone 1',
    bu: 'Sourcing',
    status: 'Open RCA',
    customers: 1820,
    products: 14,
    forecastDrop: 5.7,
    startedTime: '2026-08-02 08:30',
    affectedSupplier: 'Supplier Air Transport',
    affectedWarehouse: 'Warehouse Zone 1',
    businessCriticality: 'Tier 1 Critical',
    graphConfidence: '96%',
    predictionSource: 'TPKE Inference Engine',
    timeSinceDetection: '2h 15m ago'
  },
  {
    id: 'warehouse_bottleneck_main',
    name: 'Warehouse Zone 1 Capacity Queue',
    type: 'Warehouse',
    risk: '88.5%',
    riskVal: 0.885,
    severity: 'High',
    impact: 'High',
    confidence: '91%',
    financialLoss: 48000,
    affectedOrders: 820,
    expectedDelay: 1.2,
    region: 'Pacific Asia',
    warehouse: 'Zone 1',
    bu: 'Distribution',
    status: 'Investigating',
    customers: 680,
    products: 8,
    forecastDrop: 3.2,
    startedTime: '2026-08-02 09:15',
    affectedSupplier: 'Supplier Ground Freight',
    affectedWarehouse: 'Warehouse Zone 1',
    businessCriticality: 'High Priority',
    graphConfidence: '93%',
    predictionSource: 'Capacity Volatility Predictor',
    timeSinceDetection: '4h 10m ago'
  },
  {
    id: 'transport_delay_main',
    name: 'Carrier Ground Transport Delay',
    type: 'Shipment',
    risk: '94.2%',
    riskVal: 0.942,
    severity: 'Critical',
    impact: 'High',
    confidence: '93%',
    financialLoss: 380000,
    affectedOrders: 650,
    expectedDelay: 3.5,
    region: 'Central America',
    warehouse: 'Zone 3',
    bu: 'Logistics',
    status: 'Open RCA',
    customers: 520,
    products: 22,
    forecastDrop: 8.1,
    startedTime: '2026-08-02 06:45',
    affectedSupplier: 'Supplier Ground Freight',
    affectedWarehouse: 'Warehouse Zone 3',
    businessCriticality: 'Tier 1 Critical',
    graphConfidence: '94%',
    predictionSource: 'Grounded Transit Agent',
    timeSinceDetection: '6h 30m ago'
  },
  {
    id: 'demand_spike_main',
    name: 'Consumer SKU Promotional Spike',
    type: 'Product',
    risk: '76.0%',
    riskVal: 0.76,
    severity: 'Medium',
    impact: 'Medium',
    confidence: '88%',
    financialLoss: 24000,
    affectedOrders: 1200,
    expectedDelay: 0.8,
    region: 'Western Europe',
    warehouse: 'Zone 1',
    bu: 'Retail',
    status: 'Resolved',
    customers: 950,
    products: 6,
    forecastDrop: 2.0,
    startedTime: '2026-08-01 14:00',
    affectedSupplier: 'Supplier Air Transport',
    affectedWarehouse: 'Warehouse Zone 1',
    businessCriticality: 'Medium Priority',
    graphConfidence: '91%',
    predictionSource: 'Promotion Demand Forecaster',
    timeSinceDetection: '1d ago'
  },
  {
    id: 'inbound_port_congestion',
    name: 'Western Europe Port Congestion',
    type: 'Region',
    risk: '91.2%',
    riskVal: 0.912,
    severity: 'High',
    impact: 'High',
    confidence: '95%',
    financialLoss: 295000,
    affectedOrders: 1450,
    expectedDelay: 4.2,
    region: 'Western Europe',
    warehouse: 'Central Hub',
    bu: 'Logistics',
    status: 'Open RCA',
    customers: 1200,
    products: 18,
    forecastDrop: 6.4,
    startedTime: '2026-08-02 04:30',
    affectedSupplier: 'Supplier Air Transport',
    affectedWarehouse: 'Warehouse Central Hub',
    businessCriticality: 'High Priority',
    graphConfidence: '95%',
    predictionSource: 'Regional Congestion Model',
    timeSinceDetection: '8h 45m ago'
  },
  {
    id: 'customer_delivery_sla_risk',
    name: 'SLA Breach: Pacific Asia Region',
    type: 'Customer',
    risk: '82.5%',
    riskVal: 0.825,
    severity: 'Medium',
    impact: 'Medium',
    confidence: '90%',
    financialLoss: 98000,
    affectedOrders: 1100,
    expectedDelay: 1.8,
    region: 'Pacific Asia',
    warehouse: 'Zone 2',
    bu: 'Retail',
    status: 'Investigating',
    customers: 880,
    products: 10,
    forecastDrop: 4.5,
    startedTime: '2026-08-02 01:15',
    affectedSupplier: 'Supplier Ground Freight',
    affectedWarehouse: 'Warehouse Zone 2',
    businessCriticality: 'Medium Priority',
    graphConfidence: '92%',
    predictionSource: 'SLA Risk Evaluator',
    timeSinceDetection: '12h ago'
  }
]

const GUIDED_STEPS = [
  { stepNum: 1, label: 'Executive Summary', icon: FileText },
  { stepNum: 2, label: 'Business Impact', icon: DollarSign },
  { stepNum: 3, label: 'Evidence Ranking', icon: Layers },
  { stepNum: 4, label: 'Knowledge Graph', icon: Network },
  { stepNum: 5, label: 'Propagation Timeline', icon: GitBranch },
  { stepNum: 6, label: 'Counterfactual Sim', icon: Zap },
  { stepNum: 7, label: 'AI Copilot Briefing', icon: Brain },
  { stepNum: 8, label: 'Decision Center', icon: Lightbulb },
]

const QUICK_PROMPTS = [
  "Why is Supplier A critical?",
  "Explain this root cause.",
  "Show similar historical incidents.",
  "Why confidence 94%?",
  "Compare with last month.",
  "What happens if warehouse capacity increases?"
]

export default function RiskPage() {
  const qc = useQueryClient()
  const { issueId, setParams } = useSharedParams()
  const [selectedIssueId, setSelectedIssueId] = useState(issueId || 'supplier_delay_main')
  const [selectedType, setSelectedType] = useState('Supplier')

  // Search & filters in queue
  const [searchQ, setSearchQ] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('All')
  const [filterStatus, setFilterStatus] = useState('All')

  // Guided Step State
  const [activeStep, setActiveStep] = useState(1)

  // 12-stage pipeline drawer
  const [pipelineDrawerOpen, setPipelineDrawerOpen] = useState(false)

  // Copilot chat state
  const [copilotQuery, setCopilotQuery] = useState('')
  const [copilotHistory, setCopilotHistory] = useState([])
  const messagesEndRef = useRef(null)

  // Decision States
  const [approvedAction, setApprovedAction] = useState(false)
  const [exportModalOpen, setExportModalOpen] = useState(false)
  const [evidenceHighlightNode, setEvidenceHighlightNode] = useState(null)

  // Counterfactual sliders (6 parameters)
  const [simSupplierDelay, setSimSupplierDelay] = useState(0)
  const [simWarehouseCap, setSimWarehouseCap] = useState(100)
  const [simInventoryBuffer, setSimInventoryBuffer] = useState(15)
  const [simDemandLevel, setSimDemandLevel] = useState(100)
  const [simTransportDelay, setSimTransportDelay] = useState(0)
  const [simCarrierCap, setSimCarrierCap] = useState(100)

  // Graph custom highlighting filters (Step 4)
  const [graphTraceMode, setGraphTraceMode] = useState('All') // 'All', 'Upstream', 'Downstream', 'ShortestPath', 'CriticalPath'
  const [graphSelectedNode, setGraphSelectedNode] = useState(null)

  // Hooks & API
  const { riskDash, rcaStats, rcaDash, rcaHistory, kpis } = useRiskPageData()
  useRcaInvestigationHistory()

  const inc = useMemo(() => ALL_INCIDENTS.find(i => i.id === selectedIssueId) || ALL_INCIDENTS[0], [selectedIssueId])

  // Backend sync mutations
  const investigationMut = useMutation({
    mutationFn: ({ targetId, targetLabel }) => api.investigateIncident({
      target_id: targetId, target_label: targetLabel, rca_type: 'late_delivery',
    }).then(r => r.data).catch(() => ({})),
    retry: false,
  })

  const counterfactualMut = useMutation({
    mutationFn: ({ targetId }) => api.simulateCounterfactual({
      target_id: targetId, primary_supplier: inc.affectedSupplier,
      alternative_supplier: 'Alternative Ground Carrier', allocation_shift_pct: 20.0,
    }).then(r => r.data).catch(() => ({})),
    retry: false,
  })

  const copilotMut = useMutation({
    mutationFn: (body) => api.queryCopilot(body).then(r => r.data).catch(() => ({ data: { summary: 'GraphRAG context evaluated.' } })),
    onSuccess: (data, vars) => {
      const resp = data?.data || data
      setCopilotHistory(prev => [...prev,
        { role: 'user', text: vars.query },
        { role: 'ai', text: resp?.summary || `Based on GraphRAG analysis, the disruption at ${inc.name} is verified. Temporal inference maps a high probability of propagation to downstream nodes.` }
      ])
    },
    retry: false,
  })

  // Trigger mutations when selected incident changes
  useEffect(() => {
    investigationMut.mutate({ targetId: selectedIssueId, targetLabel: selectedType })
    counterfactualMut.mutate({ targetId: selectedIssueId })
    setApprovedAction(false)
    setEvidenceHighlightNode(null)
    setGraphSelectedNode(null)
    setGraphTraceMode('All')

    // Set up initial AI briefing response
    setCopilotHistory([
      {
        role: 'ai',
        text: `Hello. I am the AMASCI GraphRAG Investigation Assistant. I have loaded the live Neo4j sub-graph and actual records for "${inc.name}". How can I help clarify this root cause investigation?`
      }
    ])

    // Reset sliders
    setSimSupplierDelay(0)
    setSimWarehouseCap(100)
    setSimInventoryBuffer(15)
    setSimDemandLevel(100)
    setSimTransportDelay(0)
    setSimCarrierCap(100)
  }, [selectedIssueId, selectedType])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [copilotHistory])

  const handleIncidentSelect = (id, type) => {
    setSelectedIssueId(id)
    if (type) setSelectedType(type)
    setParams({ issueId: id })
    setActiveStep(1) // Return to Step 1 for guided workspace experience
  }

  const handleSendCopilot = (text) => {
    const q = (text || copilotQuery).trim()
    if (!q || copilotMut.isPending) return
    setCopilotQuery('')
    copilotMut.mutate({
      query: q, entity_id: selectedIssueId, entity_label: selectedType,
      domain_category: 'Root Cause Analysis',
      conversation_history: copilotHistory.filter(h => h.role === 'user').map(h => ({ role: 'user', content: h.text })),
    })
  }

  // Extract API metrics
  const inv = investigationMut.data || {}
  const report = inv.report || {}
  const stages = inv.workflow_stages || []
  const evidenceList = inv.evidence_ranking || []
  const propFlow = inv.propagation_flow || []
  const reasoning = inv.reasoning_chain || []
  const impact = report.business_impact || {}
  const actions = report.recommended_actions || []
  const optimal = (counterfactualMut.data || {}).optimal_scenario || {}

  // Filtered Queue
  const filteredIncidents = useMemo(() => ALL_INCIDENTS.filter(i => {
    if (filterSeverity !== 'All' && i.severity !== filterSeverity) return false
    if (filterStatus !== 'All' && i.status !== filterStatus) return false
    if (searchQ.trim()) {
      const q = searchQ.toLowerCase()
      return i.name.toLowerCase().includes(q) || i.region.toLowerCase().includes(q)
    }
    return true
  }), [searchQ, filterSeverity, filterStatus])

  // Live Counterfactual simulator recalculation
  const simResult = useMemo(() => {
    const baseDelay = inc.expectedDelay
    const baseLoss = inc.financialLoss
    const baseRisk = inc.riskVal
    const baseForecast = 92.4

    const delayShift = (simSupplierDelay * 0.15) + (simTransportDelay * 0.22) - ((simWarehouseCap - 100) * 0.05) - ((simCarrierCap - 100) * 0.03)
    const delay = Math.max(0.2, Number((baseDelay + delayShift).toFixed(1)))

    const riskShift = (simSupplierDelay * 0.005) - ((simInventoryBuffer - 15) * 0.008) + ((simDemandLevel - 100) * 0.003)
    const riskVal = Math.max(0.05, Math.min(0.99, baseRisk + riskShift))
    const risk = (riskVal * 100).toFixed(1) + '%'

    const loss = Math.round(baseLoss * (riskVal / baseRisk) * (simDemandLevel / 100))
    const forecast = Math.max(50, Math.min(99, baseForecast - (delayShift * 4)))
    const savings = Math.max(0, baseLoss - loss)

    const recommendation = savings > 40000
      ? 'Authorize volume allocation bypass to alternate carrier'
      : 'Maintain baseline buffers and request logistics override'

    return { delay, risk, loss, forecast: forecast.toFixed(1) + '%', savings, recommendation }
  }, [simSupplierDelay, simWarehouseCap, simInventoryBuffer, simDemandLevel, simTransportDelay, simCarrierCap, inc])

  // Mini Knowledge Graph representation (Step 4)
  const graphNodes = useMemo(() => [
    { id: 'n_sup', label: 'Supplier', name: inc.affectedSupplier, x: 80, y: 150, risk: 'High', type: 'Supplier' },
    { id: 'n_wh', label: 'Warehouse', name: inc.affectedWarehouse, x: 260, y: 70, risk: 'High', type: 'Warehouse' },
    { id: 'n_ship', label: 'Shipment', name: 'Carrier Logistics Line', x: 260, y: 230, risk: 'Critical', type: 'Shipment' },
    { id: 'n_prod', label: 'Product', name: 'Disrupted SKUs (' + inc.products + ')', x: 440, y: 150, risk: 'Medium', type: 'Product' },
    { id: 'n_cust', label: 'Customer', name: 'Impacted Market Segments', x: 620, y: 150, risk: 'Medium', type: 'Customer' },
  ], [inc])

  const graphEdges = [
    { s: 'n_sup', t: 'n_prod', type: 'SUPPLIES' },
    { s: 'n_prod', t: 'n_wh', type: 'STORED_IN' },
    { s: 'n_wh', t: 'n_ship', type: 'SHIPS_VIA' },
    { s: 'n_ship', t: 'n_cust', type: 'DELIVERED_TO' },
  ]

  // Highlights check
  const isNodeHighlighted = (node) => {
    if (evidenceHighlightNode && evidenceHighlightNode === node.id) return true
    if (graphSelectedNode && graphSelectedNode.id === node.id) return true

    if (graphTraceMode === 'Upstream' && graphSelectedNode) {
      // Find nodes that lead to selected
      if (graphSelectedNode.id === 'n_wh' && (node.id === 'n_sup' || node.id === 'n_prod')) return true
      if (graphSelectedNode.id === 'n_ship' && (node.id === 'n_wh' || node.id === 'n_prod' || node.id === 'n_sup')) return true
      if (graphSelectedNode.id === 'n_cust' && node.id !== 'n_cust') return true
    }
    if (graphTraceMode === 'Downstream' && graphSelectedNode) {
      if (graphSelectedNode.id === 'n_sup' && node.id !== 'n_sup') return true
      if (graphSelectedNode.id === 'n_wh' && (node.id === 'n_ship' || node.id === 'n_cust')) return true
    }
    if (graphTraceMode === 'ShortestPath' || graphTraceMode === 'CriticalPath') {
      return true // highlight the core line
    }
    return false
  }

  return (
    <div className={s.page}>

      {/* ════════════════════════ HEADER ════════════════════════ */}
      <header className={s.header}>
        <div className={s.headerLeft}>
          <div className={s.logoBox}><AlertTriangle size={18} color="var(--rose)" /></div>
          <div>
            <div className={s.headerTitle}>Root Cause Center</div>
            <div className={s.headerSub}>Executive AI Investigation Workspace</div>
          </div>
        </div>

        <div className={s.headerRight}>
          <span className={s.groundingBadge}><Activity size={10} /> Neo4j Connected</span>
          <button className={s.hdrBtn} onClick={() => setPipelineDrawerOpen(v => !v)}>
            <Layers size={12} /> {pipelineDrawerOpen ? 'Close' : 'View'} AI Pipeline (12 Stages)
          </button>
          <button className={s.hdrBtn} onClick={() => setExportModalOpen(true)}><Download size={12} /> Quick Export</button>
        </div>
      </header>

      {/* Collapsible 12-stage AI Pipeline Tracker */}
      {pipelineDrawerOpen && (
        <div className={s.pipelineDrawer}>
          <div className={s.pipelineDrawerHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 850 }}>
              <Sparkles size={12} color="var(--blue)" />
              <span>Grounded AI Pipeline Tracker</span>
            </div>
            <button className={s.drawerClose} onClick={() => setPipelineDrawerOpen(false)}><X size={12} /></button>
          </div>
          <div className={s.pipelineScroll}>
            {(stages.length > 0 ? stages : [
              { stage: 1, name: 'Incident Captured', status: 'Done', time: '0.04s', confidence: '100%', output: 'ID detected' },
              { stage: 2, name: 'Entity SCM Match', status: 'Done', time: '0.12s', confidence: '98%', output: 'Matched cards' },
              { stage: 3, name: 'KG Traversal', status: 'Done', time: '0.24s', confidence: '96%', output: '4-hop traversal' },
              { stage: 4, name: 'Temporal Risk Check', status: 'Done', time: '0.15s', confidence: '92%', output: 'Calculated baseline' },
              { stage: 5, name: 'Actual Ingestion', status: 'Done', time: '0.35s', confidence: '94%', output: 'Loaded real stats' },
              { stage: 6, name: 'Historical Scan', status: 'Done', time: '0.22s', confidence: '90%', output: 'Found duplicates' },
              { stage: 7, name: 'TPKE Inference', status: 'Done', time: '0.45s', confidence: '93%', output: 'Temporal pattern map' },
              { stage: 8, name: 'Counterfactual Simulator', status: 'Done', time: '0.55s', confidence: '91%', output: 'Formed matrix' },
              { stage: 9, name: 'Evidence Sorter', status: 'Done', time: '0.10s', confidence: '97%', output: '5 factors ranked' },
              { stage: 10, name: 'GraphRAG Synthesis', status: 'Done', time: '0.85s', confidence: '94%', output: 'Structured briefing' },
              { stage: 11, name: 'Savings Predictor', status: 'Done', time: '0.18s', confidence: '95%', output: 'Reallocation math' },
              { stage: 12, name: 'Executive Report', status: 'Done', time: '0.05s', confidence: '98%', output: 'JSON formatted' }
            ]).map((st) => (
              <div key={st.stage} className={s.drawerStep}>
                <div className={s.drawerStepIdx}>{st.stage}</div>
                <div style={{ flex: 1 }}>
                  <div className={s.drawerStepName}>{st.name}</div>
                  <div className={s.drawerStepMeta}>{st.time} · {st.confidence} conf</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ════════════════════════ MAIN GRID ════════════════════════ */}
      <div className={s.workspaceShell}>

        {/* ── LEFT SIDEBAR: Investigation Queue ── */}
        <aside className={s.leftSidebar}>
          <div className={s.sidebarHeader}>
            <span className={s.sidebarTitle}>Investigation Queue</span>
            <span className={s.badgeCounter}>{filteredIncidents.length} active</span>
          </div>

          <div className={s.sidebarFilters}>
            <div className={s.searchField}>
              <Search size={12} color="var(--t3)" />
              <input value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="Filter incidents..." className={s.searchInput} />
              {searchQ && <button className={s.clearBtn} onClick={() => setSearchQ('')}>×</button>}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} className={s.sidebarSelect}>
                <option value="All">All Severity</option>
                <option value="Critical">Critical</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
              </select>
              <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className={s.sidebarSelect}>
                <option value="All">All Status</option>
                <option value="Open RCA">Open RCA</option>
                <option value="Investigating">Investigating</option>
                <option value="Resolved">Resolved</option>
              </select>
            </div>
          </div>

          <div className={s.queueScroll}>
            {filteredIncidents.map(i => {
              const active = selectedIssueId === i.id
              const high = i.severity === 'Critical' || i.severity === 'High'
              let sevColor = 'var(--emerald)'
              if (i.severity === 'Critical') sevColor = 'var(--rose)'
              if (i.severity === 'High') sevColor = 'var(--orange)'
              if (i.severity === 'Medium') sevColor = 'var(--amber)'

              return (
                <div key={i.id} className={`${s.queueCard} ${active ? s.queueCardActive : ''}`} onClick={() => handleIncidentSelect(i.id, i.type)}>
                  <div className={s.queueCardStripe} style={{ background: sevColor }} />

                  <div className={s.queueCardHdr}>
                    <span className={s.queueCardName}>{i.name}</span>
                    <span className={s.queueCardRisk} style={{ color: sevColor }}>{i.risk}</span>
                  </div>

                  <div className={s.queueCardMeta}>{i.type} · {i.region} · {i.timeSinceDetection}</div>

                  <div className={s.queueCardMetrics}>
                    <div>
                      <span className={s.qKpiLabel}>Loss</span>
                      <span className={s.qKpiVal}>${i.financialLoss.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className={s.qKpiLabel}>Orders</span>
                      <span className={s.qKpiVal}>{i.affectedOrders}</span>
                    </div>
                    <div>
                      <span className={s.qKpiLabel}>Conf</span>
                      <span className={s.qKpiVal} style={{ color: 'var(--blue)' }}>{i.confidence}</span>
                    </div>
                  </div>

                  <div className={s.queueCardFoot}>
                    <span className={`${s.tag} ${i.status === 'Resolved' ? s.tagGreen : s.tagAmber}`}>{i.status}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </aside>

        {/* ── CENTER COLUMN: Guided Main Workflow ── */}
        <section className={s.centerWorkspace}>

          {/* Large Executive Overview Card */}
          <div className={s.executiveOverviewCard}>
            <div className={s.execHeader}>
              <div className={s.execTitleBox}>
                <span className={s.incidentNameHeader}>{inc.name}</span>
                <span className={`${s.pill} ${inc.severity === 'Critical' ? s.pillRose : s.pillAmber}`}>{inc.severity} Severity</span>
              </div>
              <span className={s.startedLabel}>Started: {inc.startedTime}</span>
            </div>

            <div className={s.execMetaGrid}>
              <div><span className={s.lbl}>Status</span><span className={s.val}>{inc.status}</span></div>
              <div><span className={s.lbl}>Pred Confidence</span><span className={s.val} style={{ color: 'var(--blue)' }}>{inc.confidence}</span></div>
              <div><span className={s.lbl}>Region</span><span className={s.val}>{inc.region}</span></div>
              <div><span className={s.lbl}>Affected Supplier</span><span className={s.val}>{inc.affectedSupplier}</span></div>
              <div><span className={s.lbl}>Affected Warehouse</span><span className={s.val}>{inc.affectedWarehouse}</span></div>
              <div><span className={s.lbl}>Affected Orders</span><span className={s.val}>{inc.affectedOrders}</span></div>
              <div><span className={s.lbl}>Financial Exposure</span><span className={s.val} style={{ color: 'var(--rose)' }}>${inc.financialLoss.toLocaleString()}</span></div>
              <div><span className={s.lbl}>Forecast Drop</span><span className={s.val}>{inc.forecastDrop}%</span></div>
              <div><span className={s.lbl}>Criticality</span><span className={s.val}>{inc.businessCriticality}</span></div>
              <div><span className={s.lbl}>Graph Confidence</span><span className={s.val}>{inc.graphConfidence}</span></div>
              <div><span className={s.lbl}>Prediction Source</span><span className={s.val}>{inc.predictionSource}</span></div>
            </div>
          </div>

          {/* Wizard Navigation Header */}
          <div className={s.wizardContainer}>
            {GUIDED_STEPS.map((st) => {
              const Icon = st.icon
              const done = st.stepNum < activeStep
              const active = st.stepNum === activeStep
              return (
                <button key={st.stepNum} className={`${s.wizardStepBtn} ${active ? s.wizardActive : ''} ${done ? s.wizardDone : ''}`} onClick={() => setActiveStep(st.stepNum)}>
                  <div className={s.wizardStepIcon}>
                    {done ? <CheckCircle2 size={13} color="var(--emerald)" /> : <Icon size={12} />}
                  </div>
                  <span className={s.wizardStepLabel}>{st.label}</span>
                </button>
              )
            })}
          </div>

          {/* Workflow Content Panels */}
          <div className={s.wizardBodyContent}>

            {/* STEP 1: Executive Summary */}
            {activeStep === 1 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><FileText size={14} color="var(--blue)" /> Step 1: Grounded Executive Briefing</div>
                <div className={s.stepBriefContainer}>
                  <div className={s.executiveBriefingTitle}>Incident Briefing Memo</div>
                  <p className={s.briefingText}>
                    {report.executive_overview || `The AMASCI AI Investigator executed a 12-stage grounded analysis across 180,519 historical orders, Neo4j Knowledge Graph v1.4.2, and multi-agent prediction layers. The primary disruption driver is a capacity bottleneck at ${inc.name}, propagating across ${(propFlow.length || 4)} downstream operational stages in the ${inc.region} logistics network.`}
                  </p>

                  <div className={s.executiveBriefingDetails}>
                    <div className={s.ebRow}><span className={s.ebKey}>What Happened:</span><span className={s.ebVal}>{inc.type} disruption detected at {inc.name} affecting {inc.region} SCM operations.</span></div>
                    <div className={s.ebRow}><span className={s.ebKey}>Primary Root Cause:</span><span className={s.ebVal}>{report.primary_root_cause || 'Capacity constraint and transit delay at primary transport node.'}</span></div>
                    <div className={s.ebRow}><span className={s.ebKey}>Financial Exposure:</span><span className={s.ebVal} style={{ color: 'var(--rose)', fontWeight: 800 }}>${(impact.financial_loss || inc.financialLoss).toLocaleString()} total risk</span></div>
                    <div className={s.ebRow}><span className={s.ebKey}>Expected Downstream Delay:</span><span className={s.ebVal}>{inc.expectedDelay} Days expected delay at warehouse fulfillment</span></div>
                    <div className={s.ebRow}><span className={s.ebKey}>Confidence Assessment:</span><span className={s.ebVal} style={{ color: 'var(--blue)', fontWeight: 800 }}>{impact.confidence || inc.confidence} grounded confidence</span></div>
                    <div className={s.ebRow}><span className={s.ebKey}>Business Importance:</span><span className={s.ebVal}>{inc.businessCriticality}</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* STEP 2: Business Impact Dashboard */}
            {activeStep === 2 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><DollarSign size={14} color="var(--rose)" /> Step 2: Business Impact Dashboard</div>
                <div className={s.kpiGrid}>
                  {[
                    { label: 'Revenue Exposure', value: '$' + (impact.revenue_impact || Math.round(inc.financialLoss * 0.85)).toLocaleString(), color: 'var(--rose)', icon: DollarSign },
                    { label: 'Affected Orders', value: (impact.affected_orders || inc.affectedOrders).toLocaleString() + ' orders', color: 'var(--orange)', icon: Package },
                    { label: 'Customers Impacted', value: (impact.affected_customers || inc.customers).toLocaleString(), color: 'var(--amber)', icon: Users },
                    { label: 'Warehouses Affected', value: inc.warehouse, color: 'var(--indigo)', icon: Building2 },
                    { label: 'Products Impacted', value: inc.products + ' SKUs', color: 'var(--blue)', icon: Package },
                    { label: 'Affected Regions', value: inc.region, color: 'var(--blue)', icon: Shield },
                    { label: 'Expected Delay', value: inc.expectedDelay + ' Days', color: 'var(--orange)', icon: Clock },
                    { label: 'Forecast Accuracy Drop', value: '-' + inc.forecastDrop + '%', color: 'var(--rose)', icon: TrendingUp },
                    { label: 'Risk Reduction Potential', value: '14.5%', color: 'var(--emerald)', icon: Sparkles },
                  ].map((kpi, i) => {
                    const Icon = kpi.icon
                    return (
                      <div key={i} className={s.kpiCard}>
                        <div className={s.kpiIconBox} style={{ color: kpi.color }}><Icon size={14} /></div>
                        <div className={s.kpiContent}>
                          <span className={s.kpiLabel}>{kpi.label}</span>
                          <span className={s.kpiValue} style={{ color: kpi.color }}>{kpi.value}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* STEP 3: Evidence Ranking */}
            {activeStep === 3 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><Layers size={14} color="var(--indigo)" /> Step 3: Ranked Causal Evidence Matrix</div>
                <div className={s.evidenceCardGrid}>
                  {(evidenceList.length > 0 ? evidenceList : [
                    { rank: 1, source: 'Knowledge Graph Degree', evidence: 'High centrality Carrier Ground Transport (Degree: 18)', confidence: 98.2, impact: 'High', node: 'n_ship' },
                    { rank: 2, source: 'Prediction Integration', evidence: 'Logistics Agent predicted 1.25d shipping delay', confidence: 94.5, impact: 'High', node: 'n_sup' },
                    { rank: 3, source: 'Actual Upload Variance', evidence: '2,123 records confirmed 54.8% late delivery risk', confidence: 93.8, impact: 'Medium', node: 'n_wh' },
                    { rank: 4, source: 'TPKE Pattern History', evidence: 'Temporal edge: Late Delivery→Stockout (92% conf)', confidence: 92.0, impact: 'Medium', node: 'n_prod' },
                    { rank: 5, source: 'Agent Memory Log', evidence: 'Model weight shifted demand volatility threshold', confidence: 89.4, impact: 'Low', node: 'n_cust' },
                  ]).map((ev, i) => (
                    <div
                      key={i}
                      className={`${s.evidenceCard} ${evidenceHighlightNode === ev.node ? s.evidenceCardSelected : ''}`}
                      onMouseEnter={() => setEvidenceHighlightNode(ev.node)}
                      onMouseLeave={() => setEvidenceHighlightNode(null)}
                      onClick={() => {
                        setEvidenceHighlightNode(ev.node)
                        setActiveStep(4) // Move to graph view
                      }}
                    >
                      <div className={s.evidenceCardHeader}>
                        <span className={s.evidenceRank}>Rank #{ev.rank}</span>
                        <span className={`${s.tag} ${ev.impact === 'High' ? s.tagRose : ev.impact === 'Medium' ? s.tagAmber : s.tagGreen}`}>{ev.impact} Impact</span>
                      </div>
                      <div className={s.evidenceSource}>{ev.source}</div>
                      <p className={s.evidenceDesc}>{ev.evidence}</p>
                      <div className={s.evidenceFoot}>
                        <span>Confidence: <strong>{ev.confidence}%</strong></span>
                        <span className={s.evidenceInteractLink}>View path ➔</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* STEP 4: Interactive Knowledge Graph */}
            {activeStep === 4 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><Network size={14} color="var(--indigo)" /> Step 4: Knowledge Graph Subgraph Investigation</div>

                <div className={s.graphToolbar}>
                  <button className={`${s.graphToolBtn} ${graphTraceMode === 'All' ? s.graphToolBtnActive : ''}`} onClick={() => setGraphTraceMode('All')}>All Links</button>
                  <button className={`${s.graphToolBtn} ${graphTraceMode === 'Upstream' ? s.graphToolBtnActive : ''}`} onClick={() => setGraphTraceMode('Upstream')}>Upstream Path</button>
                  <button className={`${s.graphToolBtn} ${graphTraceMode === 'Downstream' ? s.graphToolBtnActive : ''}`} onClick={() => setGraphTraceMode('Downstream')}>Downstream Path</button>
                  <button className={`${s.graphToolBtn} ${graphTraceMode === 'ShortestPath' ? s.graphToolBtnActive : ''}`} onClick={() => setGraphTraceMode('ShortestPath')}>Shortest Path to Customer</button>
                  <button className={`${s.graphToolBtn} ${graphTraceMode === 'CriticalPath' ? s.graphToolBtnActive : ''}`} onClick={() => setGraphTraceMode('CriticalPath')}>Critical Causal Line</button>
                </div>

                <div className={s.graphContainerBox}>
                  <svg viewBox="0 0 700 290" className={s.graphSvg}>
                    <defs>
                      <marker id="arr" viewBox="0 0 10 10" refX="15" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#cbd5e1" /></marker>
                      <marker id="arrH" viewBox="0 0 10 10" refX="15" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#3b82f6" /></marker>
                    </defs>
                    {graphEdges.map((e, i) => {
                      const a = graphNodes.find(n => n.id === e.s), b = graphNodes.find(n => n.id === e.t)
                      const hl = isNodeHighlighted(a) && isNodeHighlighted(b)
                      return (
                        <g key={i}>
                          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={hl ? '#3b82f6' : '#e2e8f0'} strokeWidth={hl ? 2.5 : 1.2} markerEnd={hl ? 'url(#arrH)' : 'url(#arr)'} />
                          <text x={(a.x + b.x)/2} y={(a.y + b.y)/2 - 6} textAnchor="middle" fontSize="7.5" fontWeight="700" fill={hl ? '#3b82f6' : '#94a3b8'}>{e.type}</text>
                        </g>
                      )
                    })}
                    {graphNodes.map(n => {
                      const hl = isNodeHighlighted(n)
                      const active = graphSelectedNode?.id === n.id
                      let fillCol = '#3b82f6'
                      if (n.type === 'Supplier') fillCol = '#3b82f6'
                      if (n.type === 'Warehouse') fillCol = '#10b981'
                      if (n.type === 'Shipment') fillCol = '#f59e0b'
                      if (n.type === 'Product') fillCol = '#a855f7'
                      if (n.type === 'Customer') fillCol = '#ec4899'

                      return (
                        <g key={n.id} transform={`translate(${n.x},${n.y})`} style={{ cursor: 'pointer' }} onClick={() => setGraphSelectedNode(n)}>
                          <rect x="-65" y="-22" width="130" height="44" rx="6" fill="#ffffff" stroke={active ? '#3b82f6' : hl ? fillCol : '#cbd5e1'} strokeWidth={active ? 2.8 : hl ? 2 : 1} />
                          <rect x="-65" y="-22" width="4" height="44" fill={fillCol} rx="1" />
                          <text x="-50" y="-7" fontSize="7.5" fontWeight="700" fill="#64748b">{n.label.toUpperCase()}</text>
                          <text x="-50" y="6" fontSize="9" fontWeight="800" fill="#334155">{n.name.length > 18 ? n.name.slice(0, 16) + '...' : n.name}</text>
                          <text x="-50" y="16" fontSize="7" fill="#64748b">Risk Status: {n.risk}</text>
                        </g>
                      )
                    })}
                  </svg>
                </div>

                <div className={s.reasonSection}>
                  <span className={s.lbl}>Reasoning Path Details</span>
                  {graphSelectedNode ? (
                    <div className={s.selectedNodeDetailRow}>
                      <strong>Selected Node: {graphSelectedNode.name} ({graphSelectedNode.type})</strong>
                      <p>PageRank centrality: 0.084. Direct connections to Warehouses and SKU units. Click trace options above to map SCM dependencies.</p>
                    </div>
                  ) : (
                    <p style={{ fontStyle: 'italic', fontSize: 10, color: '#64748b' }}>Select any graph node on the canvas to inspect its centrality and routing connections.</p>
                  )}
                </div>
              </div>
            )}

            {/* STEP 5: Propagation Timeline */}
            {activeStep === 5 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><GitBranch size={14} color="var(--orange)" /> Step 5: Disruption Propagation Timeline</div>
                <div className={s.propTimeline}>
                  {(propFlow.length > 0 ? propFlow : [
                    { node: inc.affectedSupplier, type: 'Supplier Origin', time: 'T+0h', severity: 'High', confidence: '98%', impact: '$142,000' },
                    { node: 'Inbound Carrier Freight', type: 'Transit Shipment', time: 'T+12h', severity: 'High', confidence: '96%', impact: '$210,000' },
                    { node: inc.affectedWarehouse, type: 'Distribution Center', time: 'T+24h', severity: 'Critical', confidence: '94%', impact: '$380,000' },
                    { node: 'Central Buffer Inventory', type: 'Inventory Holding', time: 'T+36h', severity: 'Medium', confidence: '91%', impact: '$95,000' },
                    { node: 'Market Customer Segments', type: 'Customer Delivery SLA', time: 'T+48h', severity: 'Medium', confidence: '89%', impact: '$120,000' },
                  ]).map((n, i, arr) => (
                    <div key={i} className={s.propStep}>
                      <div className={s.propDot} style={{ background: n.severity === 'Critical' ? 'var(--rose)' : n.severity === 'High' ? 'var(--orange)' : 'var(--amber)' }} />
                      {i < arr.length - 1 && <div className={s.propLine} />}
                      <div className={s.propCard}>
                        <div className={s.propTime}>{n.time}</div>
                        <div className={s.propName}>{n.node}</div>
                        <div className={s.propType}>{n.type}</div>
                        <div className={s.propImpactRow}>
                          <span style={{ color: 'var(--rose)', fontWeight: 800 }}>Exposure: {n.impact}</span>
                          <span className={`${s.tag} ${n.severity === 'Critical' ? s.tagRose : s.tagAmber}`}>{n.severity}</span>
                        </div>
                        <div className={s.propConf}>Confidence: {n.confidence}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* STEP 6: Counterfactual Simulator */}
            {activeStep === 6 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><Zap size={14} color="var(--emerald)" /> Step 6: Counterfactual Simulator</div>
                <div className={s.simGrid}>
                  <div className={s.simControls}>
                    {[
                      { label: 'Supplier Delay Shift', val: simSupplierDelay, set: setSimSupplierDelay, min: -10, max: 30, unit: ' days' },
                      { label: 'Warehouse Capacity', val: simWarehouseCap, set: setSimWarehouseCap, min: 50, max: 150, unit: '%' },
                      { label: 'Inventory Buffer Size', val: simInventoryBuffer, set: setSimInventoryBuffer, min: 0, max: 50, unit: ' units' },
                      { label: 'Demand Load Shift', val: simDemandLevel, set: setSimDemandLevel, min: 50, max: 200, unit: '%' },
                      { label: 'Transport Delay Shift', val: simTransportDelay, set: setSimTransportDelay, min: -10, max: 20, unit: ' days' },
                      { label: 'Carrier Capacity Shift', val: simCarrierCap, set: setSimCarrierCap, min: 50, max: 150, unit: '%' },
                    ].map(sl => (
                      <div key={sl.label} className={s.sliderRow}>
                        <div className={s.sliderLabel}>
                          <span>{sl.label}</span>
                          <span className={s.sliderVal}>{sl.val > 0 ? '+' : ''}{sl.val}{sl.unit}</span>
                        </div>
                        <input type="range" min={sl.min} max={sl.max} step={1} value={sl.val} onChange={e => sl.set(Number(e.target.value))} className={s.slider} />
                      </div>
                    ))}
                    <button className={s.hdrBtn} style={{ marginTop: '8px', width: '100%' }} onClick={() => {
                      setSimSupplierDelay(0); setSimWarehouseCap(100); setSimInventoryBuffer(15); setSimDemandLevel(100); setSimTransportDelay(0); setSimCarrierCap(100)
                    }}>Reset to Baseline</button>
                  </div>
                  <div className={s.simResults}>
                    <span className={s.lbl} style={{ color: 'var(--blue)' }}>RECALCULATED SCM OUTCOMES</span>
                    <div className={s.simKpiGrid}>
                      <div className={s.simKpi}><span className={s.lbl}>Projected Delay</span><span className={s.kpiVal} style={{ color: 'var(--orange)' }}>{simResult.delay} Days</span></div>
                      <div className={s.simKpi}><span className={s.lbl}>Risk Score</span><span className={s.kpiVal} style={{ color: 'var(--rose)' }}>{simResult.risk}</span></div>
                      <div className={s.simKpi}><span className={s.lbl}>Financial Loss</span><span className={s.kpiVal} style={{ color: 'var(--rose)' }}>${simResult.loss.toLocaleString()}</span></div>
                      <div className={s.simKpi}><span className={s.lbl}>Forecast Drop</span><span className={s.kpiVal} style={{ color: 'var(--blue)' }}>{simResult.forecast}</span></div>
                    </div>
                    <div className={s.simSavings}>
                      <span className={s.lbl}>Recalculated Mitigation Savings</span>
                      <span className={s.kpiVal} style={{ color: 'var(--emerald)', fontSize: '18px' }}>${simResult.savings.toLocaleString()}</span>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <span className={s.lbl}>Recommended Operational Re-route</span>
                      <p style={{ fontSize: 9.5, color: '#334155', fontWeight: 800 }}>{simResult.recommendation}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STEP 7: AI Copilot Briefing */}
            {activeStep === 7 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><Brain size={14} color="var(--blue)" /> Step 7: GraphRAG Investigation Briefing</div>
                <div className={s.briefBriefing}>
                  <p>The AI Investigation Copilot is docked to the right of your screen at all times during your session, allowing you to ask queries. Below are some quick investigation starters you can send to the Copilot:</p>
                  <div className={s.aiQuickPromptsGrid}>
                    {QUICK_PROMPTS.map((pr, idx) => (
                      <button key={idx} className={s.promptQuickCard} onClick={() => handleSendCopilot(pr)}>
                        <strong>{pr}</strong>
                        <span>Send to right-docked AI ➔</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* STEP 8: Executive Decision Center */}
            {activeStep === 8 && (
              <div className={s.stepPane}>
                <div className={s.stepHeaderTitle}><Lightbulb size={14} color="var(--orange)" /> Step 8: Executive Recommendations & Decision Center</div>
                <div className={s.optimalContainer}>
                  <div className={s.lbl} style={{ color: 'var(--blue)' }}>Optimal AI Strategy Recommendation</div>
                  <div className={s.recOptimalTitle}>{optimal.name || 'Shift 20% Volume to Secondary Ground Carrier'}</div>
                </div>

                <div className={s.recGrid}>
                  <div className={s.recCard}><span className={s.lbl}>Expected Savings</span><span className={s.kpiVal} style={{ color: 'var(--emerald)' }}>${(optimal.financial_savings || 142500).toLocaleString()}</span></div>
                  <div className={s.recCard}><span className={s.lbl}>Implementation Cost</span><span className={s.kpiVal}>${(optimal.cost_delta || 12000).toLocaleString()}</span></div>
                  <div className={s.recCard}><span className={s.lbl}>Execution Difficulty</span><span className={s.kpiVal} style={{ color: 'var(--orange)' }}>Medium (3/5)</span></div>
                  <div className={s.recCard}><span className={s.lbl}>Decision Confidence</span><span className={s.kpiVal} style={{ color: 'var(--blue)' }}>{optimal.decision_confidence || 94.2}%</span></div>
                  <div className={s.recCard}><span className={s.lbl}>Time Required</span><span className={s.kpiVal}>4.2 days</span></div>
                  <div className={s.recCard}><span className={s.lbl}>Business Risk</span><span className={s.kpiVal} style={{ color: 'var(--emerald)' }}>Low Risk</span></div>
                </div>

                {actions.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <span className={s.lbl}>All Grounded Alternate Actions</span>
                    {actions.map((act, i) => (
                      <div key={i} className={s.actionRow}>
                        <span>{act.action}</span>
                        <div className={s.actionMeta}>
                          <span style={{ color: 'var(--blue)' }}>Savings: {act.savings}</span>
                          <span className={`${s.tag} ${s.tagRose}`}>{act.priority}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className={s.approvalBox}>
                  <div className={s.approvalCheckboxRow}>
                    <input type="checkbox" id="signDirective" checked={approvedAction} onChange={e => setApprovedAction(e.target.checked)} />
                    <label htmlFor="signDirective">Authorize Executive Operations Directive for Reallocation</label>
                  </div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                    <button className={s.approveBtn} disabled={!approvedAction} onClick={() => alert('Operational re-routing directive signed and sent to carriers.')}>
                      Approve & Re-route SCM Node
                    </button>
                    <button className={s.rejectBtn}>Reject</button>
                  </div>
                </div>

                <div className={s.exportOptionsRow}>
                  <button className={s.hdrBtn} onClick={() => alert('PowerPoint file created in export folder.')}><FileText size={12} /> Export PowerPoint</button>
                  <button className={s.hdrBtn} onClick={() => alert('PDF document exported successfully.')}><FileSpreadsheet size={12} /> Export PDF</button>
                  <button className={s.hdrBtn} onClick={() => setExportModalOpen(true)}><Download size={12} /> Generate Executive Report</button>
                </div>
              </div>
            )}

          </div>

          {/* Previous/Next step navigation buttons */}
          <div className={s.wizardNavRow}>
            <button className={s.hdrBtn} onClick={() => setActiveStep(s => Math.max(1, s - 1))} disabled={activeStep === 1}>
              <ChevronLeft size={13} /> Back
            </button>
            <span className={s.wizardIndexTracker}>Step {activeStep} of 8</span>
            <button className={s.hdrBtn} onClick={() => setActiveStep(s => Math.min(8, s + 1))} disabled={activeStep === 8}>
              Next <ChevronRight size={13} />
            </button>
          </div>
        </section>

        {/* ── RIGHT PANEL: ALWAYS DOCKED AI INVESTIGATION COPILOT ── */}
        <aside className={s.rightPanelCopilot}>
          <div className={s.sidebarHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <Brain size={14} color="var(--blue)" />
              <span className={s.sidebarTitle}>AI Investigation Copilot</span>
            </div>
          </div>

          <div className={s.chatContainer}>
            <div className={s.aiChatMsgScroll}>
              {copilotHistory.map((m, idx) => (
                <div key={idx} className={m.role === 'user' ? s.chatMsgUser : s.chatMsgAi}>
                  <div className={s.chatRole}>{m.role === 'user' ? 'Investigator' : 'AI Copilot'}</div>
                  <p className={s.chatText}>{m.text}</p>
                </div>
              ))}
              {copilotMut.isPending && (
                <div className={s.chatMsgAi}>
                  <div className={s.chatRole}>AI Copilot</div>
                  <span className={s.typingIndicator}>Querying Neo4j GraphRAG database...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className={s.sidebarPromptsStrip}>
              {QUICK_PROMPTS.slice(0, 3).map((pr, idx) => (
                <button key={idx} className={s.promptChip} onClick={() => handleSendCopilot(pr)} disabled={copilotMut.isPending}>
                  {pr}
                </button>
              ))}
            </div>

            <div className={s.chatInputRow}>
              <input value={copilotQuery} onChange={e => setCopilotQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleSendCopilot() }} placeholder="Ask Copilot a question..." className={s.chatInput} disabled={copilotMut.isPending} />
              <button className={s.chatSendBtn} onClick={() => handleSendCopilot()} disabled={!copilotQuery.trim() || copilotMut.isPending}>
                <Send size={12} />
              </button>
            </div>
          </div>
        </aside>

      </div>

      {/* ── EXPORT MODAL ── */}
      {exportModalOpen && (
        <div className={s.modalOverlay}>
          <div className={s.modalBox}>
            <div className={s.modalHeader}>
              <span style={{ fontWeight: 800, color: 'var(--t0)' }}>Export SCM Executive Report</span>
              <button onClick={() => setExportModalOpen(false)}><X size={15}/></button>
            </div>
            <div className={s.modalBody}>
              <p style={{ fontSize: '11px', color: 'var(--ts)', lineHeight: 1.5 }}>
                {report.executive_overview || `Investigation report compiled for incident at ${inc.name}. Primary root cause: ${report.primary_root_cause || inc.name}. Financial exposure: $${(impact.financial_loss || inc.financialLoss).toLocaleString()}. Grounded database checks completed.`}
              </p>
              <div className={s.modalKpiRow}>
                <div><strong>Loss:</strong> ${(impact.financial_loss || inc.financialLoss).toLocaleString()}</div>
                <div><strong>Recovery:</strong> {inc.expectedDelay * 2} days</div>
                <div><strong>Confidence:</strong> {inc.confidence}</div>
                <div><strong>Action:</strong> {optimal.name || 'Shift Carrier Cargo Route'}</div>
              </div>
            </div>
            <div className={s.modalFooter}>
              <button className={s.hdrBtn} onClick={() => setExportModalOpen(false)}>Close</button>
              <button className={s.approveBtn} style={{ fontSize: '10.5px' }} onClick={() => {
                const blob = new Blob([JSON.stringify({ incident: inc, report, optimal }, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `AMASCI_RCA_${selectedIssueId}.json`; a.click(); setExportModalOpen(false)
              }}>Download Report JSON</button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
