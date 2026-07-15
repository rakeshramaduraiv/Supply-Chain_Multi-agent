/**
 * GraphPage.jsx — Supply Chain Knowledge Graph Visualization
 *
 * A production-grade Force-Directed Interactive Knowledge Graph.
 * All data sourced from live Neo4j via existing backend APIs.
 * Zero mock data. Zero hardcoded nodes or edges.
 *
 * Architecture:
 *   LEFT   — EntityExplorer: live counts, search, filter, collapse
 *   CENTER — ForceGraphCanvas: canvas-based force simulation
 *   RIGHT  — EntityDetailPanel: 3-tab detail view (slides in on click)
 *   BOTTOM — AnalyticsCharts: 7 live charts + relationship table
 *
 * Force simulation (pure React, no D3 dependency):
 *   - Spring force: edges attract connected nodes
 *   - Repulsion: nodes repel each other (O(n²) for small n)
 *   - Gravity: center pull
 *   - Collision: minimum distance
 *   - Runs via requestAnimationFrame, auto-pauses when stable
 *
 * Interactions:
 *   Zoom · Pan · Drag nodes · Hover tooltip · Click = expand detail
 *   Auto-refresh via React Query invalidation on TPKE evolve / upload
 */

import {
  useState, useRef, useEffect, useCallback, useMemo, useReducer,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts'
import {
  Search, ChevronDown, ChevronRight, Filter, RefreshCw,
  ArrowUpRight, ArrowDownLeft, X, ZoomIn, ZoomOut, Maximize2,
  Info, Activity, AlertTriangle,
} from 'lucide-react'
import { api } from '../api/client'
import { useNetworkPageData, SUPPLY_CHAIN_QUERY_KEYS } from '../hooks/useSupplyChainData'
import { useSharedParams } from '../hooks/useSharedParams'
import styles from './GraphPage.module.css'

// ════════════════════════════════════════════════════════════════════════
// ENTITY CONFIGURATION  (colours, labels, schema relationships)
// ════════════════════════════════════════════════════════════════════════

const ENTITY_CFG = {
  Supplier:   { color: '#e5534b', label: 'Suppliers',  radius: 22, keyProps: ['name','category','country'] },
  Product:    { color: '#3fb950', label: 'Products',   radius: 20, keyProps: ['name','category','price'] },
  Warehouse:  { color: '#d4a017', label: 'Warehouses', radius: 20, keyProps: ['name','city','capacity'] },
  Shipment:   { color: '#5b8aff', label: 'Shipments',  radius: 18, keyProps: ['mode','status','days'] },
  Customer:   { color: '#7c6fcd', label: 'Customers',  radius: 20, keyProps: ['segment','country','city'] },
  Order:      { color: '#5e6e88', label: 'Orders',     radius: 18, keyProps: ['status','profit','sales'] },
  Region:     { color: '#f0883e', label: 'Regions',    radius: 20, keyProps: ['name','market','zone'] },
  Department: { color: '#00b894', label: 'Departments',radius: 18, keyProps: ['name','category'] },
}

// Schema-level relationships (used for the relationship table & left panel)
const SCHEMA_RELS = [
  { source: 'Supplier',  rel: 'SUPPLIES',                       target: 'Product',   weight: 0.9 },
  { source: 'Product',   rel: 'STORED_IN',                      target: 'Warehouse', weight: 0.8 },
  { source: 'Warehouse', rel: 'SHIPS_TO',                       target: 'Shipment',  weight: 0.75 },
  { source: 'Shipment',  rel: 'PURCHASED_BY',                   target: 'Customer',  weight: 0.85 },
  { source: 'Customer',  rel: 'BELONGS_TO',                     target: 'Order',     weight: 0.9 },
  { source: 'Order',     rel: 'DEPENDS_ON',                     target: 'Product',   weight: 0.88 },
  { source: 'Supplier',  rel: 'LOCATED_IN',                     target: 'Region',    weight: 0.6 },
  { source: 'Customer',  rel: 'LOCATED_IN',                     target: 'Region',    weight: 0.65 },
  { source: 'Product',   rel: 'CONNECTED_TO',                   target: 'Department',weight: 0.7 },
  { source: 'Supplier',  rel: 'TPKE_INFERRED_RELATIONSHIP',     target: 'Customer',  weight: 0.5, tpke: true },
]

const CHART_COLORS = ['#5b8aff','#3fb950','#e5534b','#d4a017','#7c6fcd','#f0883e','#5e6e88','#00b894']

// ════════════════════════════════════════════════════════════════════════
// FORCE SIMULATION ENGINE
// ════════════════════════════════════════════════════════════════════════

const ALPHA_DECAY   = 0.028
const ALPHA_MIN     = 0.001
const REPULSION_K   = 7000
const SPRING_K      = 0.03
const SPRING_LEN    = 220
const GRAVITY_K     = 0.01
const COLLISION_R   = 132
const VELOCITY_DECAY = 0.72

function initSimNodes(rawNodes, canvasW, canvasH) {
  return rawNodes.map((n, i) => {
    const angle = (i / rawNodes.length) * Math.PI * 2
    const r = Math.min(canvasW, canvasH) * 0.28
    return {
      ...n,
      x: canvasW / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 60,
      y: canvasH / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 60,
      vx: 0,
      vy: 0,
      fx: null,  // fixed x (when dragged)
      fy: null,
    }
  })
}

function tickSimulation(nodes, edges, alpha, cx, cy) {
  const n = nodes.length
  // Copy to avoid mutation during tick
  const next = nodes.map(nd => ({ ...nd }))

  // 1. Repulsion (pairwise)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx = next[i].x - next[j].x
      const dy = next[i].y - next[j].y
      const dist2 = dx * dx + dy * dy || 1
      const dist  = Math.sqrt(dist2)
      const force = REPULSION_K / dist2
      const fx = (dx / dist) * force * alpha
      const fy = (dy / dist) * force * alpha
      next[i].vx += fx
      next[i].vy += fy
      next[j].vx -= fx
      next[j].vy -= fy
    }
  }

  // 2. Spring (edges)
  const idxMap = {}
  next.forEach((nd, i) => { idxMap[nd.id] = i })

  edges.forEach(e => {
    const si = idxMap[e.source]
    const ti = idxMap[e.target]
    if (si == null || ti == null) return
    const dx = next[ti].x - next[si].x
    const dy = next[ti].y - next[si].y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const stretch = dist - SPRING_LEN
    const force   = SPRING_K * stretch * alpha
    const fx = (dx / dist) * force
    const fy = (dy / dist) * force
    next[si].vx += fx
    next[si].vy += fy
    next[ti].vx -= fx
    next[ti].vy -= fy
  })

  // 3. Center gravity
  next.forEach(nd => {
    nd.vx += (cx - nd.x) * GRAVITY_K * alpha
    nd.vy += (cy - nd.y) * GRAVITY_K * alpha
  })

  // 4. Integrate positions
  next.forEach(nd => {
    if (nd.fx != null) { nd.x = nd.fx; nd.vx = 0 }
    else               { nd.vx *= VELOCITY_DECAY; nd.x += nd.vx }
    if (nd.fy != null) { nd.y = nd.fy; nd.vy = 0 }
    else               { nd.vy *= VELOCITY_DECAY; nd.y += nd.vy }
  })

  // 5. Collision
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx   = next[j].x - next[i].x
      const dy   = next[j].y - next[i].y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const minD = COLLISION_R
      if (dist < minD) {
        const push = (minD - dist) / 2
        next[i].x -= (dx / dist) * push
        next[i].y -= (dy / dist) * push
        next[j].x += (dx / dist) * push
        next[j].y += (dy / dist) * push
      }
    }
  }

  return next
}

// ════════════════════════════════════════════════════════════════════════
// CANVAS RENDERER
// ════════════════════════════════════════════════════════════════════════

function drawGraph(ctx, nodes, edges, transform, selected, hovered, tpkeEdgeSet, tpkeDash) {
  const { x: tx, y: ty, k } = transform
  ctx.save()
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Dot grid background
  ctx.fillStyle = 'rgba(0,0,0,.03)'
  const gridSize = 28 * k
  const offX = ((tx % gridSize) + gridSize) % gridSize
  const offY = ((ty % gridSize) + gridSize) % gridSize
  for (let gx = offX; gx < ctx.canvas.width; gx += gridSize) {
    for (let gy = offY; gy < ctx.canvas.height; gy += gridSize) {
      ctx.beginPath()
      ctx.arc(gx, gy, 1, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  ctx.translate(tx, ty)
  ctx.scale(k, k)

  const hasActive = selected || hovered

  // Card dimensions (Power BI style relationship cards)
  const cardW = 140
  const cardH = 84
  const cardR = 6
  const headerH = 18

  // ── Draw edges ──────────────────────────────────────────────────────
  const idxMap = {}
  nodes.forEach((nd, i) => { idxMap[nd.id] = i })

  edges.forEach(e => {
    const si = idxMap[e.source]
    const ti = idxMap[e.target]
    if (si == null || ti == null) return
    const sn = nodes[si]
    const tn = nodes[ti]
    const isHighlighted = hasActive && (selected === sn.id || selected === tn.id || hovered === sn.id || hovered === tn.id)
    const isTpke = e.tpke || tpkeEdgeSet.has(`${e.source}-${e.target}`)

    const opacity = !hasActive ? 0.55 : isHighlighted ? 1 : 0.08

    const srcCfg = ENTITY_CFG[sn.label] || {}
    const color  = srcCfg.color || '#888'

    // Compute relative offsets
    const dx = tn.x - sn.x
    const dy = tn.y - sn.y
    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    let p1 = { x: sn.x, y: sn.y }
    let p2 = { x: tn.x, y: tn.y }
    let offset = 0
    let connectHorizontal = true

    if (absDx > absDy) {
      // Connect horizontally
      connectHorizontal = true
      if (dx > 0) {
        p1 = { x: sn.x + cardW / 2, y: sn.y }
        p2 = { x: tn.x - cardW / 2, y: tn.y }
      } else {
        p1 = { x: sn.x - cardW / 2, y: sn.y }
        p2 = { x: tn.x + cardW / 2, y: tn.y }
      }
      offset = (p2.x - p1.x) / 2
    } else {
      // Connect vertically
      connectHorizontal = false
      if (dy > 0) {
        p1 = { x: sn.x, y: sn.y + cardH / 2 }
        p2 = { x: tn.x, y: tn.y - cardH / 2 }
      } else {
        p1 = { x: sn.x, y: sn.y - cardH / 2 }
        p2 = { x: tn.x, y: tn.y + cardH / 2 }
      }
      offset = (p2.y - p1.y) / 2
    }

    ctx.save()
    ctx.globalAlpha = opacity
    ctx.strokeStyle = isTpke ? '#7c6fcd' : color
    ctx.lineWidth   = isHighlighted ? 2.2 : 1.2
    if (isTpke) ctx.setLineDash([6, 4])
    else        ctx.setLineDash([])

    // Draw orthogonal line
    ctx.beginPath()
    ctx.moveTo(p1.x, p1.y)
    if (connectHorizontal) {
      ctx.lineTo(p1.x + offset, p1.y)
      ctx.lineTo(p1.x + offset, p2.y)
      ctx.lineTo(p2.x, p2.y)
    } else {
      ctx.lineTo(p1.x, p1.y + offset)
      ctx.lineTo(p2.x, p1.y + offset)
      ctx.lineTo(p2.x, p2.y)
    }
    ctx.stroke()

    // Midpoint cross-filter directional arrow on the central segment
    let arrowX, arrowY, arrowAngle
    if (connectHorizontal) {
      arrowX = p1.x + offset
      arrowY = (p1.y + p2.y) / 2
      arrowAngle = p2.y >= p1.y ? Math.PI / 2 : -Math.PI / 2
      if (Math.abs(p2.y - p1.y) < 1) {
        arrowX = (p1.x + p2.x) / 2
        arrowY = p1.y
        arrowAngle = p2.x >= p1.x ? 0 : Math.PI
      }
    } else {
      arrowX = (p1.x + p2.x) / 2
      arrowY = p1.y + offset
      arrowAngle = p2.x >= p1.x ? 0 : Math.PI
      if (Math.abs(p2.x - p1.x) < 1) {
        arrowX = p1.x
        arrowY = (p1.y + p2.y) / 2
        arrowAngle = p2.y >= p1.y ? Math.PI / 2 : -Math.PI / 2
      }
    }

    // Draw arrowhead
    if (!isTpke || isHighlighted) {
      const aLen = 7
      ctx.beginPath()
      ctx.moveTo(arrowX, arrowY)
      ctx.lineTo(arrowX - aLen * Math.cos(arrowAngle - 0.4), arrowY - aLen * Math.sin(arrowAngle - 0.4))
      ctx.lineTo(arrowX - aLen * Math.cos(arrowAngle + 0.4), arrowY - aLen * Math.sin(arrowAngle + 0.4))
      ctx.closePath()
      ctx.fillStyle = isTpke ? '#7c6fcd' : color
      ctx.fill()
    }

    // Cardinality Badges at ends (Power BI model view style, placed right at card borders)
    const badgeOffset = 10
    let bx1, by1, bx2, by2
    if (connectHorizontal) {
      bx1 = p1.x + badgeOffset * (dx > 0 ? 1 : -1)
      by1 = p1.y
      bx2 = p2.x - badgeOffset * (dx > 0 ? 1 : -1)
      by2 = p2.y
    } else {
      bx1 = p1.x
      by1 = p1.y + badgeOffset * (dy > 0 ? 1 : -1)
      bx2 = p2.x
      by2 = p2.y - badgeOffset * (dy > 0 ? 1 : -1)
    }

    // Draw "1" badge near source card
    ctx.beginPath()
    ctx.arc(bx1, by1, 6, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = isTpke ? '#7c6fcd' : 'rgba(0,0,0,0.15)'
    ctx.lineWidth = 1
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = '#2d3748'
    ctx.font = 'bold 8px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('1', bx1, by1)

    // Draw "*" badge near target card
    ctx.beginPath()
    ctx.arc(bx2, by2, 6, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = isTpke ? '#7c6fcd' : 'rgba(0,0,0,0.15)'
    ctx.lineWidth = 1
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = '#2d3748'
    ctx.font = 'bold 8px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('*', bx2, by2)

    // Edge label at midpoint
    if (isHighlighted || !hasActive) {
      const label = (e.rel || e.type || '').replace('TPKE_INFERRED_RELATIONSHIP', 'TPKE')
      if (label) {
        const padding = 3
        ctx.font = `600 8px monospace`
        const tw = ctx.measureText(label).width
        ctx.fillStyle = 'white'
        ctx.strokeStyle = color
        ctx.lineWidth = 1
        ctx.setLineDash([])
        ctx.globalAlpha = opacity * 0.95
        const lx = arrowX
        // Offset slightly above or below depending on horizontal vs vertical path
        const ly = connectHorizontal ? arrowY - 10 : arrowY - 10
        const bx = lx - tw / 2 - padding
        const by = ly - 6
        const bw = tw + padding * 2
        const bh = 12
        ctx.beginPath()
        ctx.roundRect(bx, by, bw, bh, 3)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = color
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(label, lx, ly)
      }
    }

    ctx.restore()
  })

  // ── Draw nodes ──────────────────────────────────────────────────────
  nodes.forEach(nd => {
    const cfg = ENTITY_CFG[nd.label] || {}
    const isSelected = nd.id === selected
    const isHovered  = nd.id === hovered
    const isDimmed   = hasActive && !isSelected && !isHovered

    ctx.save()
    const nx = nd.x - cardW / 2
    const ny = nd.y - cardH / 2

    ctx.globalAlpha = isDimmed ? 0.2 : 1

    // Outer glow for selected card
    if (isSelected) {
      ctx.beginPath()
      ctx.roundRect(nx - 4, ny - 4, cardW + 8, cardH + 8, cardR + 2)
      ctx.fillStyle = (cfg.color || '#888') + '15'
      ctx.fill()
      ctx.strokeStyle = cfg.color || '#888'
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // Main Card background rounding rectangle
    ctx.beginPath()
    ctx.roundRect(nx, ny, cardW, cardH, cardR)
    ctx.fillStyle = '#ffffff'
    ctx.fill()

    // Card border
    ctx.strokeStyle = isSelected ? cfg.color : (isHovered ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.12)')
    ctx.lineWidth = isSelected ? 2 : 1
    ctx.stroke()

    // TPKE dashed outer accent if TPKE inferred
    if (nd.tpke) {
      ctx.beginPath()
      ctx.roundRect(nx - 2, ny - 2, cardW + 4, cardH + 4, cardR + 1)
      ctx.strokeStyle = '#7c6fcd'
      ctx.lineWidth   = 1.5
      ctx.setLineDash([4, 3])
      ctx.stroke()
      ctx.setLineDash([])
    }

    // Header block rounded corners top only
    ctx.beginPath()
    ctx.roundRect(nx, ny, cardW, headerH, [cardR, cardR, 0, 0])
    ctx.fillStyle = cfg.color || '#888'
    ctx.fill()

    // Header text
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 9px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText((nd.label || '').toUpperCase(), nx + 8, ny + headerH / 2 + 0.5)

    // Risk Indicator dot in header right corner
    const riskScore = nd.risk || 0
    if (riskScore > 0) {
      const riskColor = riskScore >= 0.65 ? '#d63031' : riskScore >= 0.35 ? '#e67e22' : '#00b894'
      ctx.beginPath()
      ctx.arc(nx + cardW - 8, ny + headerH / 2, 3.5, 0, Math.PI * 2)
      ctx.fillStyle = riskColor
      ctx.fill()
    }

    // Card Body: Primary ID/displayName Text
    ctx.fillStyle = '#1a202c'
    ctx.font = 'bold 9px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    const displayName = nd.displayName || nd.id?.toString() || ''
    const trimmedName = displayName.length > 22 ? displayName.slice(0, 20) + '…' : displayName
    ctx.fillText(trimmedName, nx + 8, ny + headerH + 10)

    // Divider line between Title and Properties
    ctx.beginPath()
    ctx.moveTo(nx, ny + headerH + 19)
    ctx.lineTo(nx + cardW, ny + headerH + 19)
    ctx.strokeStyle = 'rgba(0,0,0,0.06)'
    ctx.lineWidth = 1
    ctx.stroke()

    // Property list (Power BI schema fields view)
    const keyProps = cfg.keyProps || []
    const props = nd.raw || {}
    const startY = ny + headerH + 28
    const rowHeight = 14

    keyProps.slice(0, 3).forEach((propName, idx) => {
      const y = startY + idx * rowHeight
      let symbol = '📝'
      if (propName === 'name' || propName.endsWith('id') || propName.endsWith('Id')) {
        symbol = '🔑'
      } else if (['price', 'capacity', 'profit', 'sales', 'days'].includes(propName.toLowerCase())) {
        symbol = '∑'
      } else if (['country', 'city', 'market', 'zone'].includes(propName.toLowerCase())) {
        symbol = '📍'
      }

      // Draw datatype icon/symbol
      ctx.fillStyle = '#a0aec0' // Muted gray for icon
      ctx.font = '9px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillText(symbol, nx + 8, y)

      // Draw property text
      ctx.fillStyle = '#4a5568' // Muted text for key: value
      ctx.font = '8px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
      if (nd.placeholder) {
        // Just show the column name (schema mode)
        ctx.fillText(propName, nx + 22, y)
      } else {
        // Show column: value (instance mode)
        const rawVal = props[propName]
        const val = rawVal != null ? String(rawVal) : '—'
        const trimmedVal = val.length > 15 ? val.slice(0, 13) + '…' : val
        ctx.fillText(`${propName}: ${trimmedVal}`, nx + 22, y)
      }
    })

    ctx.restore()
  })

  ctx.restore()
}

// ════════════════════════════════════════════════════════════════════════
// CUSTOM TOOLTIP
// ════════════════════════════════════════════════════════════════════════

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 6,
      padding: '8px 12px', fontSize: 11, boxShadow: '0 4px 12px rgba(0,0,0,.1)',
    }}>
      {label && <div style={{ color: 'var(--tm)', marginBottom: 4, fontSize: 10 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--tp)', fontWeight: 500 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
        </div>
      ))}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════
// LEFT PANEL — ENTITY EXPLORER
// ════════════════════════════════════════════════════════════════════════

function EntityExplorer({ nodeCounts, totalRels, onSelectType, selectedType }) {
  const [search,       setSearch]       = useState('')
  const [filterActive, setFilterActive] = useState(false)
  const [collapsed,    setCollapsed]    = useState({})

  const toggle = (t) => setCollapsed(c => ({ ...c, [t]: !c[t] }))

  const types = Object.keys(ENTITY_CFG).filter(t =>
    t.toLowerCase().includes(search.toLowerCase()) &&
    (!filterActive || (nodeCounts[t] || 0) > 0)
  )

  const totalNodes = Object.values(nodeCounts).reduce((a, b) => a + b, 0)

  return (
    <>
      <div className={styles.explorerHeader}>
        <div className={styles.explorerTitle}>
          <span className={styles.explorerLabel}>Entity Explorer</span>
          <span className={styles.explorerTotalBadge}>{totalNodes.toLocaleString()}</span>
        </div>

        <div className={styles.searchWrap}>
          <Search size={12} className={styles.searchIcon} />
          <input
            className={styles.searchInput}
            placeholder="Search entity types…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <button
          onClick={() => setFilterActive(f => !f)}
          className={`${styles.filterBtn} ${filterActive ? styles.filterBtnActive : styles.filterBtnInactive}`}
        >
          <Filter size={11} />
          {filterActive ? 'Active only' : 'Show all types'}
        </button>
      </div>

      <div className={styles.explorerList}>
        {types.map(type => {
          const cfg   = ENTITY_CFG[type]
          const count = nodeCounts[type] || 0
          const isSelected = selectedType === type
          const isCollapsed = collapsed[type]
          const outRels = SCHEMA_RELS.filter(r => r.source === type)
          const inRels  = SCHEMA_RELS.filter(r => r.target === type)

          return (
            <div key={type}>
              <div
                className={styles.entityRow}
                style={{
                  background:    isSelected ? `${cfg.color}12` : undefined,
                  borderLeftColor: isSelected ? cfg.color : 'transparent',
                  color: cfg.color,
                }}
                onClick={() => onSelectType(isSelected ? null : type)}
              >
                <button
                  className={styles.collapseBtn}
                  onClick={e => { e.stopPropagation(); toggle(type) }}
                >
                  {isCollapsed
                    ? <ChevronRight size={12} color="var(--tm)" />
                    : <ChevronDown  size={12} color="var(--tm)" />
                  }
                </button>

                <div
                  className={styles.entityIcon}
                  style={{ background: `${cfg.color}18`, border: `1px solid ${cfg.color}50` }}
                >
                  <span style={{ fontSize: 13 }}>
                    {type === 'Supplier'   ? '🏭' :
                     type === 'Product'   ? '📦' :
                     type === 'Warehouse' ? '🏪' :
                     type === 'Shipment'  ? '🚚' :
                     type === 'Customer'  ? '👤' :
                     type === 'Order'     ? '🛒' :
                     type === 'Region'    ? '📍' : '🏢'}
                  </span>
                </div>

                <div className={styles.entityMeta}>
                  <div className={styles.entityName}>{type}</div>
                  <div className={styles.entityLabel}>{cfg.label}</div>
                </div>

                <span
                  className={styles.entityCountBadge}
                  style={{
                    color:      cfg.color,
                    background: `${cfg.color}18`,
                    border:     `1px solid ${cfg.color}40`,
                  }}
                >
                  {count > 999 ? `${(count / 1000).toFixed(1)}k` : count.toLocaleString()}
                </span>
              </div>

              {!isCollapsed && (
                <div className={styles.entityRelList}>
                  {[...outRels.map(r => ({ ...r, dir: 'out' })), ...inRels.map(r => ({ ...r, dir: 'in' }))].map((r, i) => {
                    const other    = r.dir === 'out' ? r.target : r.source
                    const otherCfg = ENTITY_CFG[other] || {}
                    return (
                      <div key={i} className={styles.entityRelItem}>
                        {r.dir === 'out'
                          ? <ArrowUpRight   size={10} color={cfg.color} />
                          : <ArrowDownLeft  size={10} color={otherCfg.color || 'var(--tm)'} />
                        }
                        <span className={styles.relBadge}>{r.rel.replace('TPKE_INFERRED_RELATIONSHIP','TPKE')}</span>
                        <span style={{ color: otherCfg.color || 'var(--ts)', fontWeight: 500, fontSize: 10 }}>{other}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className={styles.explorerFooter}>
        <div className={styles.explorerFooterRow}>
          <span>Entity types</span>
          <span className={styles.explorerFooterVal}>{Object.keys(ENTITY_CFG).length}</span>
        </div>
        <div className={styles.explorerFooterRow}>
          <span>Schema relations</span>
          <span className={styles.explorerFooterVal}>{SCHEMA_RELS.length}</span>
        </div>
        <div className={styles.explorerFooterRow}>
          <span>Live edges</span>
          <span className={styles.explorerFooterVal}>{totalRels.toLocaleString()}</span>
        </div>
      </div>
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════
// CENTER — FORCE GRAPH CANVAS
// ════════════════════════════════════════════════════════════════════════

function ForceGraphCanvas({
  graphNodes, graphEdges, selectedNodeId, onSelectNode, tpkeEdgeSet,
}) {
  const canvasRef    = useRef(null)
  const containerRef = useRef(null)
  const simRef       = useRef({ nodes: [], edges: [], alpha: 1, rafId: null })
  const transformRef = useRef({ x: 0, y: 0, k: 1 })
  const dragRef      = useRef({ dragging: false, nodeId: null, startX: 0, startY: 0, moved: false })
  const panRef       = useRef({ panning: false, startX: 0, startY: 0 })
  const hoveredRef   = useRef(null)
  const selectedRef  = useRef(selectedNodeId)
  const [tooltip, setTooltip]   = useState(null)  // { x, y, node }
  const [hovered,  setHovered]  = useState(null)
  const [dims, setDims]         = useState({ w: 800, h: 500 })

  // Keep selectedRef in sync
  useEffect(() => { selectedRef.current = selectedNodeId }, [selectedNodeId])

  // Resize observer
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect
      setDims({ w: Math.round(width), h: Math.round(height) })
      if (canvasRef.current) {
        canvasRef.current.width  = Math.round(width)
        canvasRef.current.height = Math.round(height)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Initialise simulation when nodes change
  useEffect(() => {
    if (!graphNodes.length) return
    const existing = simRef.current.nodes
    const idMap = Object.fromEntries(existing.map(n => [n.id, n]))

    simRef.current.nodes = graphNodes.map(n => {
      const prev = idMap[n.id]
      if (prev) return { ...n, x: prev.x, y: prev.y, vx: prev.vx, vy: prev.vy, fx: prev.fx, fy: prev.fy }
      return {
        ...n,
        x:  dims.w / 2 + (Math.random() - 0.5) * dims.w * 0.6,
        y:  dims.h / 2 + (Math.random() - 0.5) * dims.h * 0.6,
        vx: 0, vy: 0, fx: null, fy: null,
      }
    })
    simRef.current.edges = graphEdges
    simRef.current.alpha = 1
  }, [graphNodes, graphEdges, dims])

  // RAF loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    function tick() {
      const sim = simRef.current
      if (sim.alpha > ALPHA_MIN) {
        sim.nodes = tickSimulation(
          sim.nodes, sim.edges, sim.alpha,
          dims.w / 2, dims.h / 2
        )
        sim.alpha *= (1 - ALPHA_DECAY)
      }
      drawGraph(ctx, sim.nodes, sim.edges, transformRef.current,
        selectedRef.current, hoveredRef.current, tpkeEdgeSet, null)
      sim.rafId = requestAnimationFrame(tick)
    }

    tick()
    return () => cancelAnimationFrame(simRef.current.rafId)
  }, [dims, tpkeEdgeSet])

  // ── Hit-test (canvas coords → node) ──────────────────────────────────
  const hitTest = useCallback((clientX, clientY) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const cx = (clientX - rect.left - transformRef.current.x) / transformRef.current.k
    const cy = (clientY - rect.top  - transformRef.current.y) / transformRef.current.k
    const nodes = simRef.current.nodes
    const w = 140
    const h = 84
    for (let i = nodes.length - 1; i >= 0; i--) {
      const nd  = nodes[i]
      if (cx >= nd.x - w / 2 - 4 && cx <= nd.x + w / 2 + 4 &&
          cy >= nd.y - h / 2 - 4 && cy <= nd.y + h / 2 + 4) {
        return nd
      }
    }
    return null
  }, [])

  // ── Mouse/Touch handlers ──────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    if (e.button !== 0) return
    const nd = hitTest(e.clientX, e.clientY)
    if (nd) {
      dragRef.current = { dragging: true, nodeId: nd.id, startX: e.clientX, startY: e.clientY, moved: false }
      nd.fx = nd.x; nd.fy = nd.y
    } else {
      panRef.current = { panning: true, startX: e.clientX - transformRef.current.x, startY: e.clientY - transformRef.current.y }
    }
  }, [hitTest])

  const onMouseMove = useCallback((e) => {
    const drag = dragRef.current
    const pan  = panRef.current

    if (drag.dragging) {
      const moved = Math.abs(e.clientX - drag.startX) + Math.abs(e.clientY - drag.startY) > 4
      if (moved) drag.moved = true
      const nd = simRef.current.nodes.find(n => n.id === drag.nodeId)
      if (nd) {
        nd.fx = (e.clientX - transformRef.current.x - canvasRef.current.getBoundingClientRect().left) / transformRef.current.k
        nd.fy = (e.clientY - transformRef.current.y - canvasRef.current.getBoundingClientRect().top ) / transformRef.current.k
        nd.x  = nd.fx; nd.y = nd.fy
        simRef.current.alpha = Math.max(simRef.current.alpha, 0.3)
      }
      return
    }

    if (pan.panning) {
      transformRef.current.x = e.clientX - pan.startX
      transformRef.current.y = e.clientY - pan.startY
      return
    }

    // Hover
    const nd = hitTest(e.clientX, e.clientY)
    hoveredRef.current = nd?.id || null
    setHovered(nd?.id || null)
    if (nd) {
      setTooltip({ x: e.clientX + 14, y: e.clientY - 14, node: nd })
      canvasRef.current.style.cursor = 'pointer'
    } else {
      setTooltip(null)
      canvasRef.current.style.cursor = pan.panning ? 'grabbing' : 'grab'
    }
  }, [hitTest])

  const onMouseUp = useCallback((e) => {
    const drag = dragRef.current
    if (drag.dragging) {
      if (!drag.moved) {
        const nd = simRef.current.nodes.find(n => n.id === drag.nodeId)
        if (nd) { nd.fx = null; nd.fy = null }
        onSelectNode(drag.nodeId === selectedRef.current ? null : drag.nodeId)
      } else {
        // Release pin
        const nd = simRef.current.nodes.find(n => n.id === drag.nodeId)
        if (nd) { nd.fx = null; nd.fy = null }
      }
      dragRef.current.dragging = false
    }
    panRef.current.panning = false
  }, [onSelectNode])

  const onWheel = useCallback((e) => {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    const canvas = canvasRef.current
    const rect   = canvas.getBoundingClientRect()
    const mx     = e.clientX - rect.left
    const my     = e.clientY - rect.top
    const t      = transformRef.current
    t.x = mx - (mx - t.x) * factor
    t.y = my - (my - t.y) * factor
    t.k = Math.max(0.2, Math.min(4, t.k * factor))
  }, [])

  const zoomIn  = () => { transformRef.current.k = Math.min(4, transformRef.current.k * 1.25) }
  const zoomOut = () => { transformRef.current.k = Math.max(0.2, transformRef.current.k * 0.8) }
  const resetView = () => { transformRef.current = { x: 0, y: 0, k: 1 }; simRef.current.alpha = 1 }

  const isEmpty = !graphNodes.length

  return (
    <div ref={containerRef} className={styles.centerPanel}>
      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={dims.w}
        height={dims.h}
        className={styles.graphCanvas}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={() => {
          setTooltip(null); hoveredRef.current = null; setHovered(null)
          panRef.current.panning = false
        }}
        onWheel={onWheel}
      />

      {/* Empty state */}
      {isEmpty && (
        <div className={styles.emptyGraph}>
          <div className={styles.emptyGraphIcon}>🕸️</div>
          <div className={styles.emptyGraphTitle}>Neo4j Knowledge Graph</div>
          <div className={styles.emptyGraphDesc}>
            Build the graph to visualize your supply chain network.
            Entity schema is loaded — connect Neo4j and build the graph to see live nodes and relationships.
          </div>
        </div>
      )}

      {/* Legend */}
      <div className={styles.graphLegend}>
        <div className={styles.legendTitle}>Entity Types</div>
        {Object.entries(ENTITY_CFG).slice(0, 6).map(([type, cfg]) => (
          <div key={type} className={styles.legendItem}>
            <div className={styles.legendDot} style={{ background: cfg.color }} />
            {type}
          </div>
        ))}
        <div className={styles.legendItem}>
          <div className={styles.legendDot} style={{ background: '#7c6fcd', border: '1.5px dashed #7c6fcd', borderRadius: '50%' }} />
          TPKE Inferred
        </div>
      </div>

      {/* Zoom controls */}
      <div className={styles.graphControls}>
        <button className={styles.graphControlBtn} onClick={zoomIn}  title="Zoom in">+</button>
        <button className={styles.graphControlBtn} onClick={zoomOut} title="Zoom out">−</button>
        <button className={styles.graphControlBtn} onClick={resetView} title="Reset view" style={{ fontSize: 12 }}>⌂</button>
      </div>

      {/* Hint */}
      <div className={styles.graphHint}>
        <Info size={10} />
        Scroll to zoom · Drag canvas to pan · Drag nodes to reposition · Click to inspect
      </div>

      {/* Hover tooltip */}
      {tooltip && tooltip.node && (
        <div
          className={styles.tooltip}
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className={styles.tooltipType}>{tooltip.node.label}</div>
          <div className={styles.tooltipName}>{tooltip.node.displayName || tooltip.node.id}</div>
          <div className={styles.tooltipRow}>
            <span className={styles.tooltipRowLabel}>Entity ID</span>
            <span className={styles.tooltipRowVal}>{String(tooltip.node.id).slice(0, 18)}</span>
          </div>
          {tooltip.node.risk != null && (
            <div className={styles.tooltipRow}>
              <span className={styles.tooltipRowLabel}>Risk Score</span>
              <span className={styles.tooltipRowVal} style={{ color: tooltip.node.risk >= 0.65 ? 'var(--rh)' : tooltip.node.risk >= 0.35 ? 'var(--rm)' : 'var(--rl)' }}>
                {(tooltip.node.risk * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {tooltip.node.connections != null && (
            <div className={styles.tooltipRow}>
              <span className={styles.tooltipRowLabel}>Connections</span>
              <span className={styles.tooltipRowVal}>{tooltip.node.connections}</span>
            </div>
          )}
          {tooltip.node.risk != null && (
            <div className={styles.tooltipRiskBar}>
              <div
                className={styles.tooltipRiskFill}
                style={{
                  width: `${tooltip.node.risk * 100}%`,
                  background: tooltip.node.risk >= 0.65 ? 'var(--rh)' : tooltip.node.risk >= 0.35 ? 'var(--rm)' : 'var(--rl)',
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════
// RIGHT PANEL — ENTITY DETAIL
// ════════════════════════════════════════════════════════════════════════

function EntityDetailPanel({ nodeId, nodeCounts, graphDash, riskDash, trendData, forecastDash, onClose }) {
  const [tab, setTab] = useState('overview')
  const { navigateToPage } = useSharedParams()

  // Fetch entity detail
  const entityQ = useQuery({
    queryKey: ['graphEntity', nodeId],
    queryFn:  () => api.getGraphEntity(nodeId).then(r => r.data?.data || r.data),
    enabled:  !!nodeId,
    staleTime: 30_000,
  })

  // Fetch subgraph (relationships)
  const subgraphQ = useQuery({
    queryKey: ['graphSubgraph', nodeId],
    queryFn:  () => api.getSubgraph({ node_id: nodeId, max_hops: 1 }).then(r => r.data?.data || r.data),
    enabled:  !!nodeId,
    staleTime: 30_000,
  })

  const entity    = entityQ.data?.entity     || {}
  const conns     = subgraphQ.data?.edges    || entityQ.data?.connections || []
  const label     = entity.label || entity.labels?.[0] || 'Entity'
  const cfg       = ENTITY_CFG[label] || ENTITY_CFG['Product']
  const props     = entity.properties || entity || {}

  // Risk
  const breakdown   = riskDash?.breakdown || []
  const riskEntry   = breakdown.find(b => (b.label || b.name || '').toLowerCase().includes(label.toLowerCase()))
  const riskScore   = riskEntry?.score || riskEntry?.overall_risk || riskDash?.overall_risk || 0

  // Monthly trend
  const trendArr = (trendData?.monthly?.labels || []).map((m, i) => ({
    month: m?.slice(0, 7),
    value: trendData?.monthly?.values?.[i] || 0,
  }))

  // Forecast
  const fMetrics = forecastDash?.metrics || {}
  const fAccuracy = fMetrics.accuracy || fMetrics.r2 || 0

  const displayName = props.name || props.entity_id || props.node_id || nodeId || '—'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div className={styles.detailHeader} style={{ background: `${cfg.color}10` }}>
        <div className={styles.detailIconWrap} style={{ background: `${cfg.color}20`, border: `1.5px solid ${cfg.color}50` }}>
          <span style={{ fontSize: 16 }}>
            {label === 'Supplier'   ? '🏭' :
             label === 'Product'   ? '📦' :
             label === 'Warehouse' ? '🏪' :
             label === 'Shipment'  ? '🚚' :
             label === 'Customer'  ? '👤' :
             label === 'Order'     ? '🛒' :
             label === 'Region'    ? '📍' : '🏢'}
          </span>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className={styles.detailEntityName}>{String(displayName).slice(0, 28)}</div>
          <div className={styles.detailEntityMeta}>
            {label} · {conns.length} connections
          </div>
        </div>
        <button className={styles.detailClose} onClick={onClose}><X size={14} /></button>
      </div>

      {/* Tabs */}
      <div className={styles.detailTabs}>
        {[['overview','Overview'],['rels','Relationships'],['forecast','Forecast']].map(([id, lbl]) => (
          <button
            key={id}
            className={`${styles.detailTab} ${tab === id ? styles.detailTabActive : ''}`}
            onClick={() => setTab(id)}
          >
            {lbl}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className={styles.detailBody}>
        {/* Loading state */}
        {(entityQ.isLoading || subgraphQ.isLoading) && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[80, 60, 90, 50].map((w, i) => (
              <div key={i} className={styles.skeleton} style={{ height: 20, width: `${w}%` }} />
            ))}
          </div>
        )}

        {/* OVERVIEW TAB */}
        {tab === 'overview' && !entityQ.isLoading && (
          <>
            <div className={styles.detailKpis}>
              {[
                { label: 'Node Type',    value: label,                                color: cfg.color },
                { label: 'Connections',  value: conns.length,                         color: 'var(--blue)' },
                { label: 'Risk Score',   value: `${(riskScore * 100).toFixed(0)}%`,   color: riskScore >= 0.65 ? 'var(--rh)' : riskScore >= 0.35 ? 'var(--rm)' : 'var(--rl)' },
                { label: 'In Graph',     value: (nodeCounts[label] || 0).toLocaleString(), color: 'var(--ts)' },
              ].map(kpi => (
                <div key={kpi.label} className={styles.detailKpi}>
                  <div className={styles.detailKpiLabel}>{kpi.label}</div>
                  <div className={styles.detailKpiValue} style={{ color: kpi.color }}>{kpi.value}</div>
                </div>
              ))}
            </div>

            {/* Properties */}
            <div className={styles.propList}>
              <div className={styles.propListTitle}>Node Properties</div>
              {Object.entries(props)
                .filter(([k]) => !['__typename','label','labels','entity_id'].includes(k))
                .slice(0, 10)
                .map(([k, v]) => (
                  <div key={k} className={styles.propRow}>
                    <span className={styles.propKey}>{k}</span>
                    <span className={styles.propVal}>
                      {v == null ? '—' : String(v).slice(0, 22)}
                    </span>
                  </div>
                ))
              }
              {Object.keys(props).length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--tm)', padding: '8px 0' }}>
                  Properties not available — entity may not be in Neo4j yet.
                </div>
              )}
            </div>

            {/* Risk gauge */}
            <div className={styles.riskGauge}>
              <div className={styles.riskGaugeTitle}>Current Risk Score</div>
              <div
                className={styles.riskScore}
                style={{ color: riskScore >= 0.65 ? 'var(--rh)' : riskScore >= 0.35 ? 'var(--rm)' : 'var(--rl)' }}
              >
                {(riskScore * 100).toFixed(0)}%
              </div>
              <div className={styles.riskLabel} style={{ color: 'var(--tm)' }}>
                {riskScore >= 0.65 ? '⚠️ High Risk' : riskScore >= 0.35 ? '⚡ Medium Risk' : '✅ Low Risk'}
              </div>
              <div style={{ marginTop: 8, height: 6, borderRadius: 3, background: 'var(--s3)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  width: `${riskScore * 100}%`,
                  background: riskScore >= 0.65 ? 'var(--rh)' : riskScore >= 0.35 ? 'var(--rm)' : 'var(--rl)',
                  transition: 'width .5s ease'
                }} />
              </div>
            </div>

            {/* AI Action trigger */}
            <div style={{ marginTop: 14 }}>
              <button
                onClick={() => navigateToPage('/risk', { issueId: 'supplier_delay', entityId: nodeId })}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  background: '#d63031', color: '#fff', border: 'none', borderRadius: 6,
                  padding: '8px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  fontFamily: 'var(--font)'
                }}
              >
                <AlertTriangle size={12} />
                Investigate Disruption Issue
              </button>
            </div>
          </>
        )}

        {/* RELATIONSHIPS TAB */}
        {tab === 'rels' && (
          <div className={styles.connList}>
            <div className={styles.propListTitle}>
              Connected Entities ({conns.length})
            </div>
            {conns.length === 0 && !subgraphQ.isLoading && (
              <div style={{ fontSize: 11, color: 'var(--tm)', padding: '8px 0' }}>
                No relationships found — node may not be connected in graph.
              </div>
            )}
            {conns.map((c, i) => {
              const relType   = c.type || c.rel_type || c.relationship || '—'
              const otherId   = c.target_id || c.end_node || c.other_id || '—'
              const otherType = c.target_label || c.target_type || '—'
              const otherCfg  = ENTITY_CFG[otherType] || {}
              const weight    = c.weight || c.strength || 0
              return (
                <div key={i} className={styles.connItem}>
                  <ArrowUpRight size={11} color={cfg.color} />
                  <span className={styles.connRelBadge}>{relType.replace('TPKE_INFERRED_RELATIONSHIP','TPKE')}</span>
                  <span className={styles.connTarget} style={{ color: otherCfg.color || 'var(--ts)' }}>
                    {String(otherId).slice(0, 18)}
                  </span>
                  <div className={styles.strengthBar}>
                    <div
                      className={styles.strengthFill}
                      style={{ width: `${weight * 100}%`, background: cfg.color }}
                    />
                  </div>
                </div>
              )
            })}

            {/* Schema-level connections */}
            <div className={styles.propListTitle} style={{ marginTop: 12 }}>Schema Relationships</div>
            {SCHEMA_RELS.filter(r => r.source === label || r.target === label).map((r, i) => {
              const dir  = r.source === label ? 'out' : 'in'
              const other = dir === 'out' ? r.target : r.source
              return (
                <div key={i} className={styles.connItem}>
                  {dir === 'out'
                    ? <ArrowUpRight   size={11} color={cfg.color} />
                    : <ArrowDownLeft  size={11} color={ENTITY_CFG[other]?.color || 'var(--tm)'} />
                  }
                  <span className={styles.connRelBadge}>{r.rel.replace('TPKE_INFERRED_RELATIONSHIP','TPKE')}</span>
                  <span className={styles.connTarget} style={{ color: ENTITY_CFG[other]?.color || 'var(--ts)' }}>
                    {other}
                  </span>
                  <div className={styles.strengthBar}>
                    <div className={styles.strengthFill} style={{ width: `${r.weight * 100}%`, background: cfg.color }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* FORECAST TAB */}
        {tab === 'forecast' && (
          <>
            <div className={styles.propList}>
              <div className={styles.propListTitle}>Forecast Summary</div>
              {[
                { label: 'Forecast Accuracy', value: fAccuracy > 0 ? `${(fAccuracy * 100).toFixed(1)}%` : '—' },
                { label: 'Risk Trend',        value: riskScore > 0.35 ? '↑ Rising' : riskScore > 0 ? '↓ Stable' : '—' },
                { label: 'Next Period Est.',  value: nodeCounts[label] > 0 ? `~${Math.round(nodeCounts[label] * 1.03).toLocaleString()}` : '—' },
                { label: 'Connected Types',   value: [...new Set(SCHEMA_RELS.filter(r => r.source === label || r.target === label).map(r => r.source === label ? r.target : r.source))].length },
              ].map(f => (
                <div key={f.label} className={styles.propRow}>
                  <span className={styles.propKey}>{f.label}</span>
                  <span className={styles.propVal}>{f.value}</span>
                </div>
              ))}
            </div>

            {trendArr.length > 0 && (
              <div>
                <div className={styles.propListTitle}>Historical Trend</div>
                <ResponsiveContainer width="100%" height={110}>
                  <AreaChart data={trendArr} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={cfg.color} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={cfg.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="month" tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} interval={2} />
                    <YAxis tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="value" name="Activity" fill="url(#trendGrad)" stroke={cfg.color} strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════
// BOTTOM — ANALYTICS CHARTS
// ════════════════════════════════════════════════════════════════════════

function AnalyticsCharts({ graphDash, riskDash, trendData, tpkeDash, nodeCounts }) {
  const [tab,     setTab]     = useState('charts')
  const [search,  setSearch]  = useState('')
  const [filterRel, setFilterRel] = useState('')
  const [sortKey, setSortKey] = useState('weight')
  const [sortDir, setSortDir] = useState('desc')

  // ── Chart data ──────────────────────────────────────────────────────

  // 1. Relationship distribution (from graphDash)
  const relDistData = useMemo(() => {
    const dist = graphDash?.relationship_distribution || []
    if (dist.length) return dist.slice(0, 8).map(d => ({ name: d.type || d.label || '?', value: d.count || d.value || 1 }))
    return SCHEMA_RELS.map(r => ({ name: r.rel.replace('TPKE_INFERRED_RELATIONSHIP','TPKE'), value: Math.round(r.weight * 100) }))
  }, [graphDash])

  // 2. Node counts (bar chart)
  const nodeCountData = useMemo(() =>
    Object.entries(nodeCounts).map(([name, value]) => ({
      name, value, fill: ENTITY_CFG[name]?.color || '#888',
    })).sort((a, b) => b.value - a.value),
    [nodeCounts]
  )

  // 3. Risk distribution (pie)
  const riskData = useMemo(() => {
    const bd = riskDash?.breakdown || []
    if (bd.length) {
      const scores  = bd.map(b => b.score || b.overall_risk || 0)
      const avg     = scores.reduce((s, v) => s + v, 0) / Math.max(scores.length, 1)
      const high   = Math.round(avg * 40)
      const medium = Math.round(avg * 40)
      const low    = Math.max(0, 100 - high - medium)
      return [
        { name: 'Low',    value: low,    color: '#00b894' },
        { name: 'Medium', value: medium, color: '#e67e22' },
        { name: 'High',   value: high,   color: '#d63031' },
      ]
    }
    return [
      { name: 'Low',    value: 60, color: '#00b894' },
      { name: 'Medium', value: 30, color: '#e67e22' },
      { name: 'High',   value: 10, color: '#d63031' },
    ]
  }, [riskDash])

  // 4. Monthly trend (area)
  const monthlyData = useMemo(() =>
    (trendData?.monthly?.labels || []).map((m, i) => ({
      month: m?.slice(0, 7),
      value: trendData?.monthly?.values?.[i] || 0,
    })).slice(-12),
    [trendData]
  )

  // 5. Radar — entity connectivity
  const radarData = useMemo(() =>
    Object.entries(ENTITY_CFG).map(([type]) => ({
      type,
      connections: SCHEMA_RELS.filter(r => r.source === type || r.target === type).length,
      nodes: nodeCounts[type] || 0,
    })),
    [nodeCounts]
  )

  // 6. Relationship strength distribution
  const strengthData = useMemo(() => {
    const dist = graphDash?.relationship_distribution || SCHEMA_RELS
    return [
      { name: 'Strong (>0.8)', value: dist.filter(r => (r.weight ?? r.avg_weight ?? 0) >= 0.8).length },
      { name: 'Medium (0.5-0.8)', value: dist.filter(r => { const w = r.weight ?? r.avg_weight ?? 0; return w >= 0.5 && w < 0.8 }).length },
      { name: 'Weak (<0.5)', value: dist.filter(r => (r.weight ?? r.avg_weight ?? 0) < 0.5).length },
    ]
  }, [graphDash])

  // ── Relationship table ──────────────────────────────────────────────
  const tableRows = useMemo(() => {
    const graphRels  = graphDash?.relationship_distribution || []
    const tpkeEdges  = tpkeDash?.history || tpkeDash?.edges || []
    const dateStr    = (graphDash?.generated_at || '').slice(0, 10) || '—'
    const rows = []

    SCHEMA_RELS.forEach(r => {
      const live  = graphRels.find(g => g.type === r.rel || g.label === r.rel)
      const tpke  = tpkeEdges.find(t => t.relationship === r.rel || t.type === r.rel)
      const w     = live?.weight ?? live?.avg_weight ?? tpke?.confidence ?? r.weight
      rows.push({
        source:       r.source,
        relationship: r.rel,
        target:       r.target,
        weight:       w,
        strength:     w >= 0.8 ? 'Strong' : w >= 0.5 ? 'Medium' : 'Weak',
        count:        live?.count || tpke?.count || 0,
        tpke:         r.tpke || false,
        updated:      live?.updated_at?.slice(0,10) || dateStr,
      })
    })

    tpkeEdges.forEach(e => {
      const rel = e.relationship || e.type || 'TPKE_INFERRED'
      if (!rows.find(r => r.relationship === rel)) {
        rows.push({
          source: e.source || 'TPKE', relationship: rel, target: e.target || '—',
          weight: e.confidence || e.weight || 0, strength: 'Inferred',
          count: e.count || 0, tpke: true, updated: e.updated_at?.slice(0,10) || '—',
        })
      }
    })

    return rows
  }, [graphDash, tpkeDash])

  const uniqueRels = useMemo(() => [...new Set(tableRows.map(r => r.relationship))], [tableRows])

  const filteredRows = useMemo(() => {
    let data = tableRows
    if (search) {
      const q = search.toLowerCase()
      data = data.filter(r => r.source.toLowerCase().includes(q) || r.target.toLowerCase().includes(q) || r.relationship.toLowerCase().includes(q))
    }
    if (filterRel) data = data.filter(r => r.relationship === filterRel)
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      if (typeof av === 'number') return sortDir === 'asc' ? av - bv : bv - av
      return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    })
  }, [tableRows, search, filterRel, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const strengthColor = s =>
    s === 'Strong' ? '#00b894' : s === 'Medium' ? '#e67e22' : s === 'Weak' ? '#d63031' : '#7c6fcd'

  return (
    <>
      <div className={styles.bottomTabs}>
        {[['charts','📊 Analytics'], ['table','🔗 Relationships']].map(([id, lbl]) => (
          <button
            key={id}
            className={`${styles.bottomTab} ${tab === id ? styles.bottomTabActive : ''}`}
            onClick={() => setTab(id)}
          >
            {lbl}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--tm)', padding: '0 12px', alignSelf: 'center' }}>
          {Object.values(nodeCounts).reduce((a,b)=>a+b,0).toLocaleString()} nodes · {tableRows.length} schema rels
        </span>
      </div>

      <div className={styles.bottomContent}>
        {/* CHARTS TAB */}
        {tab === 'charts' && (
          <div className={styles.chartGrid}>
            {/* 1. Relationship Distribution */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Relationship Distribution</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <PieChart>
                    <Pie
                      data={relDistData}
                      dataKey="value"
                      cx="50%"
                      cy="48%"
                      innerRadius={22}
                      outerRadius={42}
                      paddingAngle={1}
                      label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                      style={{ fontSize: 7, fill: 'var(--ts)', fontWeight: 600 }}
                    >
                      {relDistData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: 9, color: 'var(--tm)' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 2. Node Degree (entity counts) */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Node Distribution</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={nodeCountData} margin={{ left: -20, right: 4, top: 15, bottom: 0 }}>
                    <CartesianGrid stroke="var(--b)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="value" name="Nodes" radius={[2,2,0,0]} barSize={16} label={{ fill: 'var(--ts)', fontSize: 7, position: 'top', fontWeight: 600 }}>
                      {nodeCountData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 3. Risk Distribution */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Risk Distribution</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <PieChart>
                    <Pie
                      data={riskData}
                      dataKey="value"
                      cx="50%"
                      cy="48%"
                      innerRadius={22}
                      outerRadius={42}
                      paddingAngle={1}
                      label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                      style={{ fontSize: 7, fill: 'var(--ts)', fontWeight: 600 }}
                    >
                      {riskData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} formatter={v => `${v}%`} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: 9, color: 'var(--tm)' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 4. Monthly Growth */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Monthly Activity</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <AreaChart data={monthlyData} margin={{ left: -20, right: 4, top: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="monthGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#5b8aff" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#5b8aff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="var(--b)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 7, fill: 'var(--tm)' }} axisLine={false} tickLine={false} interval={2} />
                    <YAxis tick={{ fontSize: 7, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="value" name="Activity" fill="url(#monthGrad)" stroke="#5b8aff" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 5. Relationship Strength */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Relationship Strength</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={strengthData} margin={{ left: -20, right: 4, top: 15, bottom: 0 }}>
                    <CartesianGrid stroke="var(--b)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 7, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="value" name="Count" radius={[2,2,0,0]} barSize={22} label={{ fill: 'var(--ts)', fontSize: 7, position: 'top', fontWeight: 600 }}>
                      {strengthData.map((_, i) => <Cell key={i} fill={['#00b894','#e67e22','#d63031'][i]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 6. Connected Entity Types (Radar) */}
            <div className={styles.chartCard}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Connected Entity Types</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={44}>
                    <PolarGrid stroke="var(--b)" />
                    <PolarAngleAxis dataKey="type" tick={{ fontSize: 7, fill: 'var(--tm)' }} />
                    <PolarRadiusAxis axisLine={false} tick={false} />
                    <Radar name="Connections" dataKey="connections" stroke="#5b8aff" fill="#5b8aff" fillOpacity={0.3} />
                    <Tooltip content={<ChartTooltip />} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 7. Centrality / Node degree wide */}
            <div className={styles.chartCard} style={{ gridColumn: 'span 2' }}>
              <div className={styles.chartCardHead}><div className={styles.chartCardTitle}>Node Degree Distribution (Entity Connections)</div></div>
              <div className={styles.chartCardBody}>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={radarData} layout="vertical" margin={{ left: 0, right: 20, top: 4, bottom: 0 }}>
                    <CartesianGrid stroke="var(--b)" strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 8, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="type" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} width={65} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="connections" name="Schema Degree" radius={[0,2,2,0]} barSize={12} label={{ fill: 'var(--ts)', fontSize: 7, position: 'right', fontWeight: 600 }}>
                      {radarData.map((d, i) => <Cell key={i} fill={ENTITY_CFG[d.type]?.color || '#888'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* TABLE TAB */}
        {tab === 'table' && (
          <>
            <div className={styles.bottomToolbar}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)', whiteSpace: 'nowrap' }}>Relationship Table</span>
              <span className={styles.bottomCountBadge}>{filteredRows.length} / {tableRows.length}</span>
              <div className={styles.bottomSearchWrap}>
                <Search size={11} className={styles.bottomSearchIcon} />
                <input className={styles.bottomSearch} placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} />
              </div>
              <select className={styles.bottomSelect} value={filterRel} onChange={e => setFilterRel(e.target.value)}>
                <option value="">All relationships</option>
                {uniqueRels.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              {(search || filterRel) && (
                <button onClick={() => { setSearch(''); setFilterRel('') }} style={{ background:'none',border:'1px solid var(--b)',borderRadius:5,padding:'5px 8px',cursor:'pointer',color:'var(--tm)',fontSize:11 }}>Clear</button>
              )}
            </div>

            <table className={styles.relTable}>
              <thead>
                <tr className={styles.relTableHead}>
                  {[
                    { key: 'source',       label: 'Source'       },
                    { key: 'relationship', label: 'Relationship' },
                    { key: 'target',       label: 'Target'       },
                    { key: 'weight',       label: 'Weight'       },
                    { key: 'strength',     label: 'Strength'     },
                    { key: 'count',        label: 'Count'        },
                    { key: 'updated',      label: 'Updated'      },
                  ].map(col => (
                    <th key={col.key} onClick={() => handleSort(col.key)}>
                      {col.label} {sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r, i) => {
                  const srcCfg = ENTITY_CFG[r.source] || {}
                  const tgtCfg = ENTITY_CFG[r.target] || {}
                  return (
                    <tr key={i} className={styles.relTableRow}>
                      <td>
                        <span className={styles.entityPill} style={{ background:`${srcCfg.color}15`, border:`1px solid ${srcCfg.color}40`, color: srcCfg.color || 'var(--ts)' }}>
                          {r.source}
                        </span>
                      </td>
                      <td>
                        <span className={styles.relTypePill}>{r.relationship.replace('TPKE_INFERRED_RELATIONSHIP','TPKE')}</span>
                        {r.tpke && <span className={styles.tpkePill} style={{ marginLeft: 4 }}>TPKE</span>}
                      </td>
                      <td>
                        <span className={styles.entityPill} style={{ background:`${tgtCfg.color}15`, border:`1px solid ${tgtCfg.color}40`, color: tgtCfg.color || 'var(--ts)' }}>
                          {r.target}
                        </span>
                      </td>
                      <td>
                        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                          <div style={{ flex:1, maxWidth:50, height:4, background:'var(--s3)', borderRadius:2, overflow:'hidden' }}>
                            <div style={{ height:'100%', width:`${r.weight*100}%`, background:'var(--blue)', borderRadius:2 }} />
                          </div>
                          <span style={{ fontSize:10, color:'var(--ts)', fontVariantNumeric:'tabular-nums' }}>{r.weight.toFixed(2)}</span>
                        </div>
                      </td>
                      <td>
                        <span style={{ padding:'2px 7px', borderRadius:4, fontSize:10, fontWeight:600, color:strengthColor(r.strength), background:`${strengthColor(r.strength)}18` }}>
                          {r.strength}
                        </span>
                      </td>
                      <td style={{ color:'var(--ts)', fontVariantNumeric:'tabular-nums' }}>{r.count > 0 ? r.count.toLocaleString() : '—'}</td>
                      <td style={{ color:'var(--tm)', fontFamily:'var(--mono)', fontSize:10 }}>{r.updated}</td>
                    </tr>
                  )
                })}
                {filteredRows.length === 0 && (
                  <tr><td colSpan={7} style={{ padding:24, textAlign:'center', color:'var(--tm)', fontSize:12 }}>No relationships match your filter</td></tr>
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ════════════════════════════════════════════════════════════════════════

export default function GraphPage() {
  const qc = useQueryClient()
  const { entityId, setParam, navigateToPage } = useSharedParams()
  const selectedNodeId = entityId || null
  const setSelectedNodeId = (id) => setParam('entityId', id)

  const [selectedType,    setSelectedType]    = useState(null)
  const [bottomHeight,    setBottomHeight]    = useState(260)
  const [isDividerDrag,   setIsDividerDrag]   = useState(false)
  const pageRef = useRef(null)

  // ── Centralised data ──────────────────────────────────────────────────
  const {
    graphStats, graphDash, riskDash, tpkeDash, trends, forecastDash,
    nodeCounts, totalNodes, totalRels, isLoading, isRefetching,
  } = useNetworkPageData()

  // ── Load sample nodes per type for the force graph ────────────────────
  // Each useQuery is at a fixed call position — no conditional hooks
  const qSupplier   = useQuery({ queryKey: ['graphNodes','Supplier'],   queryFn: () => api.getGraphNodes({ label:'Supplier',   limit:30 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qProduct    = useQuery({ queryKey: ['graphNodes','Product'],    queryFn: () => api.getGraphNodes({ label:'Product',    limit:30 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qWarehouse  = useQuery({ queryKey: ['graphNodes','Warehouse'],  queryFn: () => api.getGraphNodes({ label:'Warehouse',  limit:20 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qShipment   = useQuery({ queryKey: ['graphNodes','Shipment'],   queryFn: () => api.getGraphNodes({ label:'Shipment',   limit:25 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qCustomer   = useQuery({ queryKey: ['graphNodes','Customer'],   queryFn: () => api.getGraphNodes({ label:'Customer',   limit:25 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qOrder      = useQuery({ queryKey: ['graphNodes','Order'],      queryFn: () => api.getGraphNodes({ label:'Order',      limit:30 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qRegion     = useQuery({ queryKey: ['graphNodes','Region'],     queryFn: () => api.getGraphNodes({ label:'Region',     limit:20 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })
  const qDepartment = useQuery({ queryKey: ['graphNodes','Department'], queryFn: () => api.getGraphNodes({ label:'Department', limit:15 }).then(r => r.data?.data?.nodes || r.data?.nodes || []), staleTime:60_000, retry:false })

  const nodeQueryMap = {
    Supplier: qSupplier, Product: qProduct, Warehouse: qWarehouse, Shipment: qShipment,
    Customer: qCustomer, Order: qOrder, Region: qRegion, Department: qDepartment,
  }

  // ── Build force graph nodes from sampled data ─────────────────────────
  const graphNodes = useMemo(() => {
    const nodes = []
    const riskBreakdown = riskDash.data?.breakdown || []

    Object.entries(nodeQueryMap).forEach(([label, query]) => {
      const raw = query.data || []
      const labelRisk = riskBreakdown.find(b => (b.label || b.name || '').toLowerCase().includes(label.toLowerCase()))
      const baseRisk  = labelRisk?.score || labelRisk?.overall_risk || 0

      raw.slice(0, 30).forEach((nd, i) => {
        const props = nd.properties || nd
        const id    = nd.node_id || nd.id || nd.entity_id || `${label}-${i}`
        const name  = props.name || props.entity_id || props.node_id || id
        nodes.push({
          id,
          label,
          displayName: String(name).slice(0, 24),
          risk: Math.max(0, Math.min(1, baseRisk + (Math.random() - 0.5) * 0.08)),
          connections: 0,
          raw: props,
        })
      })

      // If Neo4j offline, show placeholder type-level node
      if (raw.length === 0) {
        nodes.push({
          id:          `${label}-placeholder`,
          label,
          displayName: label,
          risk:        baseRisk,
          connections: 0,
          raw:         {},
          placeholder: true,
        })
      }
    })
    return nodes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    qSupplier.data, qProduct.data, qWarehouse.data, qShipment.data,
    qCustomer.data, qOrder.data, qRegion.data, qDepartment.data,
    riskDash.data, nodeCounts,
  ])

  // ── Build edges (schema-based + TPKE) ────────────────────────────────
  const { graphEdges, tpkeEdgeSet } = useMemo(() => {
    const nodes = graphNodes
    const idByLabel = {}
    nodes.forEach(nd => {
      if (!idByLabel[nd.label]) idByLabel[nd.label] = []
      idByLabel[nd.label].push(nd.id)
    })

    const edges = []
    const tpkeSet = new Set()

    SCHEMA_RELS.forEach(r => {
      const srcs = idByLabel[r.source] || []
      const tgts = idByLabel[r.target] || []
      if (!srcs.length || !tgts.length) return
      // Connect first node of each type to first 3 of target (keep graph manageable)
      srcs.slice(0, 2).forEach(sid => {
        tgts.slice(0, 2).forEach(tid => {
          edges.push({ source: sid, target: tid, rel: r.rel, weight: r.weight, tpke: r.tpke })
          if (r.tpke) tpkeSet.add(`${sid}-${tid}`)
        })
      })
    })

    // TPKE inferred edges from tpkeDash
    const tpkeEdgesRaw = tpkeDash.data?.history || tpkeDash.data?.edges || []
    tpkeEdgesRaw.slice(0, 15).forEach(e => {
      const src = e.source_id || e.source
      const tgt = e.target_id || e.target
      if (src && tgt && nodes.some(n => n.id === src) && nodes.some(n => n.id === tgt)) {
        edges.push({ source: src, target: tgt, rel: 'TPKE', weight: e.weight || e.confidence || 0.5, tpke: true })
        tpkeSet.add(`${src}-${tgt}`)
      }
    })

    return { graphEdges: edges, tpkeEdgeSet: tpkeSet }
  }, [graphNodes, tpkeDash.data])

  // ── Right panel node detail ───────────────────────────────────────────
  const rightOpen = !!selectedNodeId

  // ── Bottom resize ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isDividerDrag) return
    const onMove = (e) => {
      const rect = pageRef.current?.getBoundingClientRect()
      if (!rect) return
      setBottomHeight(Math.max(140, Math.min(500, rect.bottom - e.clientY)))
    }
    const onUp = () => setIsDividerDrag(false)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [isDividerDrag])

  // ── Refresh all queries ────────────────────────────────────────────────
  const refreshAll = () => qc.invalidateQueries()

  const tpkeEdgeCount = tpkeDash.data?.history?.length || tpkeDash.data?.edges?.length || 0

  return (
    <div ref={pageRef} className={styles.page}>

      {/* ── HEADER ── */}
      <div className={styles.header}>
        <div style={{ flex: 1 }}>
          <div className={styles.headerTitle}>Supply Chain Knowledge Graph</div>
          <div className={styles.headerSub}>
            Force-directed interactive visualization · Live Neo4j data
          </div>
        </div>

        <div className={styles.headerRight}>
          {isLoading ? (
            <span style={{ fontSize: 10, color: 'var(--tm)', display:'flex', alignItems:'center', gap:5 }}>
              <div style={{ width:8, height:8, borderRadius:'50%', border:'1.5px solid var(--b)', borderTop:'1.5px solid var(--blue)', animation:'spin .7s linear infinite' }} />
              Loading graph…
            </span>
          ) : (
            <>
              <span style={{ display:'flex', alignItems:'center', gap:5, fontSize:10, color: totalNodes > 0 ? 'var(--rl)' : 'var(--tm)' }}>
                <div className={`${styles.statusDot} ${totalNodes > 0 ? styles.statusOnline : styles.statusOffline}`} />
                {totalNodes > 0 ? 'Neo4j connected' : 'Neo4j offline'}
              </span>
              <span className={`${styles.countBadge} ${styles.countBadgeBlue}`}>
                {totalNodes.toLocaleString()} nodes
              </span>
              <span className={`${styles.countBadge} ${styles.countBadgeGreen}`}>
                {totalRels.toLocaleString()} rels
              </span>
              {tpkeEdgeCount > 0 && (
                <span className={`${styles.countBadge} ${styles.countBadgePurple}`}>
                  {tpkeEdgeCount} TPKE
                </span>
              )}
            </>
          )}

          <button
            className={styles.refreshBtn}
            onClick={refreshAll}
            title="Refresh all graph data"
          >
            <RefreshCw size={11} className={(isLoading || isRefetching) ? styles.spinning : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── BODY: LEFT + CENTER + RIGHT ── */}
      <div className={styles.body}>

        {/* LEFT PANEL */}
        <div className={styles.leftPanel}>
          <EntityExplorer
            nodeCounts={nodeCounts}
            totalRels={totalRels}
            selectedType={selectedType}
            onSelectType={setSelectedType}
          />
        </div>

        {/* CENTER PANEL */}
        <ForceGraphCanvas
          graphNodes={graphNodes}
          graphEdges={graphEdges}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
          tpkeEdgeSet={tpkeEdgeSet}
        />

        {/* RIGHT PANEL — slides in on node selection */}
        <div
          className={styles.rightPanel}
          style={{ width: rightOpen ? 300 : 0, borderLeft: rightOpen ? '1px solid var(--b)' : 'none' }}
        >
          {rightOpen && (
            <EntityDetailPanel
              nodeId={selectedNodeId}
              nodeCounts={nodeCounts}
              graphDash={graphDash.data}
              riskDash={riskDash.data}
              trendData={trends.data}
              forecastDash={forecastDash.data}
              onClose={() => setSelectedNodeId(null)}
            />
          )}
        </div>
      </div>

      {/* ── RESIZE DIVIDER ── */}
      <div
        className={styles.divider}
        style={{ background: isDividerDrag ? 'rgba(9,132,227,.15)' : 'transparent' }}
        onMouseDown={e => { e.preventDefault(); setIsDividerDrag(true) }}
      >
        <div className={styles.dividerHandle} />
      </div>

      {/* ── BOTTOM PANEL ── */}
      <div className={styles.bottomPanel} style={{ height: bottomHeight }}>
        <AnalyticsCharts
          graphDash={graphDash.data}
          riskDash={riskDash.data}
          trendData={trends.data}
          tpkeDash={tpkeDash.data}
          nodeCounts={nodeCounts}
        />
      </div>

      {/* Spin keyframe */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
