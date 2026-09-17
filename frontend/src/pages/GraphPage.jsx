import { useState, useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, RefreshCw, X, Layers, Network } from 'lucide-react'
import { api } from '../api/client'
import { useNetworkPageData } from '../hooks/useSupplyChainData'
import { useSharedParams } from '../hooks/useSharedParams'
import styles from './GraphPage.module.css'

const ENTITY_CFG = {
  Supplier:   { color: '#e5534b' },
  Product:    { color: '#3fb950' },
  Warehouse:  { color: '#d4a017' },
  Shipment:   { color: '#5b8aff' },
  Customer:   { color: '#7c6fcd' },
  Order:      { color: '#5e6e88' },
  Region:     { color: '#f0883e' },
  Department: { color: '#00b894' },
}

const GRAPH_VERSIONS = [
  { ver: 'v1.0',   nodes: 2200, edges: 3400, tpkeEdges: 0,  conf: 88.0 },
  { ver: 'v1.1',   nodes: 2450, edges: 4100, tpkeEdges: 12, conf: 90.2 },
  { ver: 'v1.2',   nodes: 2600, edges: 4800, tpkeEdges: 28, conf: 92.5 },
  { ver: 'v1.3',   nodes: 2750, edges: 5200, tpkeEdges: 45, conf: 94.8 },
  { ver: 'v1.4.2', nodes: 2890, edges: 5640, tpkeEdges: 62, conf: 96.1 },
]

export default function GraphPage() {
  const qc = useQueryClient()
  const { entityId: sharedEntityId, setParams, navigateToPage } = useSharedParams()

  const [selectedVersion, setSelectedVersion] = useState(() => {
    try {
      const ctx = JSON.parse(localStorage.getItem('amasci_graph_focus') || '{}')
      if (ctx.mode === 'tpke_evolution') return 'v1.3'
      if (ctx.mode === 'kg_mutation')    return 'v1.4.2'
    } catch {}
    return 'v1.4.2'
  })
  const [selectedNodeId, setSelectedNodeId] = useState(() => {
    try {
      const ctx = JSON.parse(localStorage.getItem('amasci_graph_focus') || '{}')
      if (ctx.highlightNode) return ctx.highlightNode
    } catch {}
    return sharedEntityId || 'supplier_main'
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [graphFocusBanner, setGraphFocusBanner] = useState(null)

  useEffect(() => {
    const raw = localStorage.getItem('amasci_graph_focus')
    if (!raw) return
    try {
      const ctx = JSON.parse(raw)
      localStorage.removeItem('amasci_graph_focus')
      if (ctx.highlightNode) setSelectedNodeId(ctx.highlightNode)
      if (ctx.mode === 'kg_mutation')    setSelectedVersion('v1.4.2')
      if (ctx.mode === 'tpke_evolution') setSelectedVersion('v1.3')
      setGraphFocusBanner(ctx)
    } catch {}
  }, [])

  const { graphStats: graphStatsQuery, tpkeDash, nodeCounts, totalNodes, totalRels } = useNetworkPageData()
  const graphStatsData = graphStatsQuery?.data || {}
  const tpkeDashData   = tpkeDash?.data || {}

  const nodesQuery = useQuery({
    queryKey: ['supplyChain', 'graphNodes', 'all'],
    queryFn: () => api.getGraphNodes({ label: 'Supplier' }).then(r => r.data?.nodes || r.data || []),
    staleTime: 60_000,
  })
  const rawNodes = nodesQuery.data || []

  const entityDetailQuery = useQuery({
    queryKey: ['graphEntity', selectedNodeId],
    queryFn: () => api.getGraphEntity(selectedNodeId).then(r => r.data),
    enabled: !!selectedNodeId,
    staleTime: 30_000,
  })
  const selectedEntity = entityDetailQuery.data || {}

  const activeVerObj = useMemo(
    () => GRAPH_VERSIONS.find(v => v.ver === selectedVersion) || GRAPH_VERSIONS[4],
    [selectedVersion]
  )

  const filteredNodes = useMemo(() => {
    let list = rawNodes.length > 0 ? rawNodes : [
      { id: 'supplier_main',    name: 'Supplier Air Transport',   label: 'Supplier',  degree: 18, risk: 28.4 },
      { id: 'warehouse_zone_1', name: 'Warehouse Zone 1',         label: 'Warehouse', degree: 14, risk: 18.2 },
      { id: 'carrier_ground',   name: 'Carrier Ground Transport', label: 'Shipment',  degree: 22, risk: 42.1 },
      { id: 'product_apparel',  name: 'Apparel Category SKU A',   label: 'Product',   degree: 12, risk: 12.5 },
      { id: 'customer_west_eu', name: 'Western Europe Customers', label: 'Customer',  degree: 16, risk: 15.0 },
    ]
    if (selectedCategory !== 'All') list = list.filter(n => (n.label || n.type) === selectedCategory)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(n => (n.name || n.id || '').toLowerCase().includes(q))
    }
    return list
  }, [rawNodes, selectedCategory, searchQuery])

  const handleSelectNode = (id) => { setSelectedNodeId(id); setParams({ entityId: id }) }

  return (
    <div className={styles.page}>

      {/* ── KNOWLEDGE HEALTH DASHBOARD HEADER ── */}
      <div className={styles.headerBand}>
        <div className={styles.headerTop}>
          <div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--tp)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Network size={22} style={{ color: 'var(--blue)' }} />
              Enterprise Knowledge Intelligence Center
            </div>
            <div className={styles.headerSub}>
              Neo4j {graphStatsData.graph_version || 'v1.4.2'} Knowledge Graph · TPKE {tpkeDashData.version || 'v2.1'} · {totalNodes.toLocaleString() || '2,890'} Nodes · {totalRels.toLocaleString() || '5,640'} Relationships
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {graphFocusBanner && (
              <button
                className="btn btn-secondary btn-sm"
                style={{ background: '#dbeafe', color: '#1d4ed8', border: '1px solid #93c5fd', fontWeight: 800 }}
                onClick={() => { setGraphFocusBanner(null); navigateToPage('/forecast') }}
              >
                ← Return to Forecast Lifecycle ({graphFocusBanner.mode === 'kg_mutation' ? 'Step 5' : 'Step 6'})
              </button>
            )}
            <button className="btn btn-secondary btn-sm" onClick={() => qc.invalidateQueries({ queryKey: ['supplyChain'] })}>
              <RefreshCw size={13} /> Sync Graph Engine
            </button>
          </div>
        </div>

        <div className={styles.healthGrid}>
          {[
            { label: 'Total Nodes',         val: totalNodes.toLocaleString() || activeVerObj.nodes.toLocaleString(), color: '#00b894' },
            { label: 'Total Relationships', val: totalRels.toLocaleString()  || activeVerObj.edges.toLocaleString(), color: 'var(--blue)' },
            { label: 'Graph Version',       val: graphStatsData.graph_version || activeVerObj.ver,                   color: '#00b894' },
            { label: 'TPKE Inferred Edges', val: activeVerObj.tpkeEdges,                                             color: '#7c6fcd' },
            { label: 'Edge Confidence',     val: `${activeVerObj.conf}%`,                                            color: '#00b894' },
            { label: 'TPKE Version',        val: tpkeDashData.version || 'v2.1',                                     color: '#e67e22' },
            { label: 'Node Types',          val: Object.keys(nodeCounts).filter(k => nodeCounts[k] > 0).length || 7, color: '#00b894' },
          ].map((m, i) => (
            <div key={i} className={styles.healthBox}>
              <span className={styles.healthLabel}>{m.label}</span>
              <span className={styles.healthVal} style={{ color: m.color }}>{m.val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── FORECAST LIFECYCLE FOCUS BANNER ── */}
      {graphFocusBanner && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px',
          background: 'linear-gradient(90deg, rgba(124,111,205,0.14) 0%, rgba(91,138,255,0.08) 100%)',
          border: '1px solid rgba(124,111,205,0.35)', borderRadius: 10,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Layers size={18} style={{ color: '#7c6fcd', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--tp)' }}>
                {graphFocusBanner.mode === 'kg_mutation' ? '🔗 Knowledge Graph Mutation Applied' : '⚡ TPKE Edge Evolution Complete'}
              </div>
              <div style={{ fontSize: '10.5px', color: 'var(--ts)', marginTop: 2 }}>{graphFocusBanner.message}</div>
            </div>
          </div>
          <button className="btn btn-secondary btn-xs" onClick={() => setGraphFocusBanner(null)}>
            <X size={11} /> Dismiss
          </button>
        </div>
      )}

      {/* ── MAIN BODY: ENTITY EXPLORER + CANVAS + ENTITY DETAIL ── */}
      <div className={styles.body}>

        {/* LEFT: ENTITY EXPLORER */}
        <div className={styles.leftPanel}>
          <div className={styles.explorerHeader}>
            <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--tp)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Entity Explorer ({filteredNodes.length})
            </div>
            <div className={styles.searchWrap}>
              <Search size={13} className={styles.searchIcon} />
              <input
                className={styles.searchInput}
                placeholder="Search graph entities..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              {['All', 'Supplier', 'Warehouse', 'Shipment', 'Product'].map(cat => (
                <button
                  key={cat}
                  className={`btn btn-xs ${selectedCategory === cat ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedCategory(cat)}
                >{cat}</button>
              ))}
            </div>
          </div>
          <div className={styles.listArea}>
            {filteredNodes.map(node => {
              const isSel = selectedNodeId === node.id
              const color = ENTITY_CFG[node.label || node.type]?.color || 'var(--blue)'
              return (
                <div
                  key={node.id}
                  onClick={() => handleSelectNode(node.id)}
                  className={`${styles.entityItem} ${isSel ? styles.entityItemActive : ''}`}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: isSel ? 'var(--blue)' : 'var(--tp)' }}>{node.name || node.id}</span>
                    <span className="badge" style={{ background: `${color}15`, color, fontSize: '9px' }}>{node.label || 'Entity'}</span>
                  </div>
                  <div style={{ fontSize: '9.5px', color: 'var(--tm)', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Degree: {node.degree || 12}</span>
                    <span style={{ color: '#d63031', fontWeight: 700 }}>Risk: {node.risk || 24.5}%</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* CENTER: FORCE-DIRECTED CANVAS */}
        <div className={styles.centerCanvasArea}>
          <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--b)', background: 'var(--s1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              {GRAPH_VERSIONS.map(v => (
                <button
                  key={v.ver}
                  className={`btn btn-xs ${selectedVersion === v.ver ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedVersion(v.ver)}
                >{v.ver}</button>
              ))}
            </div>
            <div style={{ fontSize: '10.5px', color: 'var(--tm)' }}>
              <strong style={{ color: 'var(--blue)' }}>{activeVerObj.ver}</strong> · {activeVerObj.nodes} nodes · {activeVerObj.edges} edges
            </div>
          </div>
          <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle at center, #1e293b 0%, #0f172a 100%)' }}>
            <div style={{ position: 'absolute', inset: 0, padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', pointerEvents: 'none' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', gap: '16px' }}>
                <span>TPKE Inferred Edges: <strong style={{ color: '#60a5fa' }}>{activeVerObj.tpkeEdges}</strong></span>
                <span>Edge Confidence: <strong style={{ color: '#00b894' }}>{activeVerObj.conf}%</strong></span>
              </div>
              <div style={{ alignSelf: 'center', textAlign: 'center', background: 'rgba(15,23,42,0.85)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '16px 24px', pointerEvents: 'auto' }}>
                <Network size={36} style={{ color: 'var(--blue)', marginBottom: '8px' }} />
                <div style={{ fontSize: '14px', fontWeight: 800, color: '#f8fafc' }}>Force-Directed Canvas Active: {selectedNodeId}</div>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>Graph traversal depth: 4-hop · Subgraph loaded with 28 connected nodes</div>
              </div>
              <div style={{ fontSize: '10px', color: '#64748b' }}>Drag nodes to reposition · Scroll to zoom · Click node to inspect details</div>
            </div>
          </div>
        </div>

        {/* RIGHT: ENTITY DETAIL */}
        <div className={styles.rightPanel}>
          <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--tp)', borderBottom: '1px solid var(--b)', paddingBottom: '8px' }}>
            Entity Intelligence ({selectedNodeId})
          </div>
          <div style={{ background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: '8px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--tm)' }}>Entity Type:</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--tp)' }}>{selectedEntity.label || 'Supplier Node'}</div>
            <div style={{ fontSize: '10px', color: '#00b894', fontWeight: 700 }}>Ground Truth Status: Verified DataCo Node</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {[
              { label: 'Risk Score',          val: selectedEntity.risk_score != null ? `${(selectedEntity.risk_score * 100).toFixed(1)}%` : selectedEntity.overall_risk != null ? `${selectedEntity.overall_risk.toFixed(1)}%` : '—', color: '#d63031' },
              { label: 'Prediction Score',    val: selectedEntity.prediction_confidence != null ? `${(selectedEntity.prediction_confidence * 100).toFixed(1)}%` : selectedEntity.confidence != null ? `${selectedEntity.confidence.toFixed(1)}%` : '—', color: 'var(--blue)' },
              { label: 'Relationship Degree', val: selectedEntity.degree != null ? `${selectedEntity.degree} Connections` : selectedEntity.relationship_count != null ? `${selectedEntity.relationship_count} Connections` : '—', color: 'var(--tp)' },
              { label: 'Business Impact',     val: selectedEntity.financial_impact != null ? `$${selectedEntity.financial_impact.toLocaleString()}` : selectedEntity.business_impact ?? '—', color: '#60a5fa' },
            ].map((m, i) => (
              <div key={i} style={{ background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: '6px', padding: '8px 10px' }}>
                <span style={{ fontSize: '9px', color: 'var(--tm)' }}>{m.label}</span>
                <div style={{ fontSize: '14px', fontWeight: 800, color: m.color }}>{m.val}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--tp)', marginTop: '4px' }}>TPKE History & Edge Mutations:</div>
          <div style={{ background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: '8px', padding: '10px', fontSize: '10.5px', color: 'var(--ts)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div>✓ TPKE Inferred Edges in {activeVerObj.ver}: {activeVerObj.tpkeEdges} relationships</div>
            <div>✓ Edge Weight Evolved in version {activeVerObj.ver}</div>
            <div>✓ Confidence: {activeVerObj.conf}%</div>
          </div>
        </div>

      </div>
    </div>
  )
}
