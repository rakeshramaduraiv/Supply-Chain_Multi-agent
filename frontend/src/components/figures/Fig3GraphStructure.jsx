// src/components/figures/Fig3GraphStructure.jsx
import { useQuery } from '@tanstack/react-query'
import { useRef, useCallback, useState, useEffect } from 'react'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT } from './figureTheme'

const ANCHOR_COLORS = {
  dept_cat_region:       PALETTE.primary,
  cat_region:            PALETTE.green,
  mode_region_country:   PALETTE.pink,
}
const ANCHOR_LABELS = {
  dept_cat_region:     'dept_cat_region',
  cat_region:          'cat_region',
  mode_region_country: 'mode_region_country',
}
// Fallback mapping from backend's internal anchor_level values
const ANCHOR_REMAP = {
  supplier_product: 'dept_cat_region',
  inventory_order:  'cat_region',
  route_logistics:  'mode_region_country',
  other:            'dept_cat_region',
}

function nodeColor(anchor) {
  const key = ANCHOR_COLORS[anchor] ? anchor : (ANCHOR_REMAP[anchor] || 'dept_cat_region')
  return ANCHOR_COLORS[key] || PALETTE.primary
}

function nodeRadius(degree) {
  return Math.max(2, Math.min(9, 2 + Math.sqrt(degree || 0) * 1.2))
}

export default function Fig3GraphStructure() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'graph-structure'],
    queryFn: () => api.getGraphStructure(800).then(r => r.data),
    staleTime: 120_000, retry: 2,
  })

  const graphRef   = useRef(null)
  const [frozen,   setFrozen]   = useState(false)
  const [showLabels, setLabels] = useState(false)
  const [fgLoaded, setFgLoaded] = useState(false)
  const [ForceGraph, setFG]     = useState(null)

  // Lazy-load react-force-graph-2d (heavy canvas lib)
  useEffect(() => {
    import('react-force-graph-2d').then(m => {
      setFG(() => m.default)
      setFgLoaded(true)
    })
  }, [])

  const nodes = (data?.nodes || []).map(n => ({
    id:     n.id,
    label:  n.label,
    anchor: ANCHOR_REMAP[n.anchor_level] || n.anchor_level || 'dept_cat_region',
    degree: n.degree || 0,
  }))
  const nodeIds = new Set(nodes.map(n => n.id))
  const links = (data?.links || [])
    .filter(l => nodeIds.has(l.source) && nodeIds.has(l.target))
    .map(l => ({ source: l.source, target: l.target, type: l.type }))
  const stats = data?.stats || {}
  const alCounts = stats.anchor_level_counts || {}

  // Remap anchor_level_counts keys to spec names
  const specCounts = {}
  for (const [k, v] of Object.entries(alCounts)) {
    const mapped = ANCHOR_REMAP[k] || k
    specCounts[mapped] = (specCounts[mapped] || 0) + v
  }

  const handleFreeze = useCallback(() => {
    if (graphRef.current) {
      if (!frozen) {
        graphRef.current.pauseAnimation()
      } else {
        graphRef.current.resumeAnimation()
      }
    }
    setFrozen(f => !f)
  }, [frozen])

  const nodeCanvasObject = useCallback((node, ctx) => {
    const r     = nodeRadius(node.degree)
    const color = nodeColor(node.anchor)
    ctx.globalAlpha = 0.88
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()
    ctx.strokeStyle = 'rgba(255,255,255,0.4)'
    ctx.lineWidth = 0.4
    ctx.stroke()
    ctx.globalAlpha = 1
    if (showLabels && r > 4) {
      ctx.font = `${Math.max(4, r * 0.9)}px sans-serif`
      ctx.fillStyle = '#333'
      ctx.textAlign = 'center'
      ctx.fillText(String(node.id).slice(0, 8), node.x, node.y + r + 6)
    }
  }, [showLabels])

  const linkColor = useCallback(() => `rgba(204,204,204,0.55)`, [])

  const empty = !isLoading && !isError && (!data || !nodes.length)
    ? 'Neo4j returned no graph — verify the knowledge graph build step.' : undefined

  const caption = stats.total_nodes
    ? `Knowledge graph spanning ${stats.total_nodes.toLocaleString()} nodes across the anchor levels (dept, cat, region), (cat, region) and (mode, region, country). Node radius scales with degree.`
    : undefined

  return (
    <FigureShell
      figureNumber={3}
      title="Knowledge Graph Structure Across Three Anchor Levels"
      emptyMessage={empty}
      loading={isLoading}
      error={isError ? 'Failed to load graph — Neo4j may be initializing' : undefined}
      caption={caption}
    >
      {/* Controls */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
        <button
          onClick={handleFreeze}
          style={{ padding: '5px 14px', fontSize: 12, fontWeight: 600, border: '1px solid #e2e8f0', borderRadius: 6, cursor: 'pointer', background: frozen ? PALETTE.primary : '#f8fafc', color: frozen ? '#fff' : '#475569' }}
        >
          {frozen ? '▶ Resume layout' : '⏸ Freeze layout'}
        </button>
        <button
          onClick={() => setLabels(l => !l)}
          style={{ padding: '5px 14px', fontSize: 12, fontWeight: 600, border: '1px solid #e2e8f0', borderRadius: 6, cursor: 'pointer', background: showLabels ? PALETTE.green : '#f8fafc', color: showLabels ? '#fff' : '#475569' }}
        >
          {showLabels ? 'Hide labels' : 'Show labels'}
        </button>
      </div>

      {/* Force graph canvas */}
      <div style={{ width: 1100, height: 560, background: '#fff', border: '1px solid #f1f5f9', borderRadius: 4, overflow: 'hidden' }}>
        {fgLoaded && ForceGraph && nodes.length > 0 && (
          <ForceGraph
            ref={graphRef}
            graphData={{ nodes, links }}
            width={1100}
            height={560}
            backgroundColor="#ffffff"
            nodeCanvasObject={nodeCanvasObject}
            nodeCanvasObjectMode={() => 'replace'}
            linkColor={linkColor}
            linkWidth={0.35}
            linkDirectionalArrowLength={0}
            enableNodeDrag={!frozen}
            enableZoomInteraction={true}
            cooldownTicks={120}
          />
        )}
        {(!fgLoaded || !nodes.length) && (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 13 }}>
            {!fgLoaded ? 'Loading graph renderer…' : 'No nodes to display'}
          </div>
        )}
      </div>

      {/* Legend below canvas — 3 columns with real counts */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginTop: 16, fontSize: FONT.legend }}>
        {Object.entries(ANCHOR_LABELS).map(([key, lbl]) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: ANCHOR_COLORS[key], display: 'inline-block' }} />
            <span style={{ color: '#333' }}>
              {lbl}&nbsp;&nbsp;({(specCounts[key] || 0).toLocaleString()} nodes)
            </span>
          </div>
        ))}
      </div>
    </FigureShell>
  )
}
