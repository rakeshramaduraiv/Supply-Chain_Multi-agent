// src/components/figures/Fig1Ablation.jsx
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LabelList, ResponsiveContainer, Cell,
} from 'recharts'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT, NO_ANIMATION, AXIS_STYLE } from './figureTheme'

// Value label above each bar
const ValLabel = ({ x, y, width, value }) => {
  if (value == null) return null
  return (
    <text x={x + width / 2} y={y - 5} textAnchor="middle"
      fontSize={FONT.footnote} fill="#222">
      {Number(value).toFixed(2)}
    </text>
  )
}

// Delta connector rendered as SVG overlay via customized tick
function DeltaConnector({ x, y, barWidth, delta }) {
  if (delta == null) return null
  const lx = x + barWidth * 0.5
  const rx = x + barWidth * 1.5 + 4
  const cy = y - 18
  return (
    <g>
      <line x1={lx} y1={cy} x2={rx} y2={cy} stroke={PALETTE.grey} strokeWidth={1.2} />
      <line x1={lx} y1={cy - 4} x2={lx} y2={cy + 4} stroke={PALETTE.grey} strokeWidth={1.2} />
      <line x1={rx} y1={cy - 4} x2={rx} y2={cy + 4} stroke={PALETTE.grey} strokeWidth={1.2} />
      <text x={(lx + rx) / 2} y={cy - 6} textAnchor="middle"
        fontSize={11.5} fontWeight="bold" fill="#111">
        {delta >= 0 ? `Δ = +${delta.toFixed(2)}` : `Δ = ${delta.toFixed(2)}`}
      </text>
    </g>
  )
}

// Custom bar shape that draws the delta connector above the WITH_GRAPH bar
function WithGraphBar(props) {
  const { x, y, width, height, payload } = props
  return (
    <g>
      <rect x={x} y={y} width={width} height={height}
        fill={PALETTE.primary} stroke="#00456e" strokeWidth={0.8} />
      {payload?.delta != null && (
        <DeltaConnector x={x} y={y} barWidth={width} delta={payload.delta} />
      )}
    </g>
  )
}

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)', minWidth: 200 }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{label} — {d?.metric_name}</div>
      {payload.map(p => (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 20, marginBottom: 3, color: p.color }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 700 }}>{p.value != null ? Number(p.value).toFixed(4) : '—'}</span>
        </div>
      ))}
      {d?.delta != null && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,.1)', color: d.delta >= 0 ? '#4ade80' : '#f87171', fontWeight: 600 }}>
          Δ = {d.delta >= 0 ? '+' : ''}{d.delta.toFixed(4)}
        </div>
      )}
      {d?.n_test_samples > 0 && (
        <div style={{ marginTop: 4, fontSize: 10, color: '#64748b' }}>{d.n_test_samples.toLocaleString()} test samples</div>
      )}
    </div>
  )
}

const AGENT_LABELS = { Demand: 'Demand (R²)', Supplier: 'Supplier (AUC)', Logistics: 'Logistics (AUC)' }

export default function Fig1Ablation() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'ablation'],
    queryFn: () => api.getAblationResults().then(r => r.data),
    staleTime: 120_000, retry: 2,
  })

  const rows = Array.isArray(data) ? data : []
  const hasSuspicious = rows.some(r => r.suspicious_identical)

  const chartData = rows.map(r => ({
    ...r,
    name: AGENT_LABELS[r.agent] || r.agent,
    graph_ablated: r.graph_ablated ?? null,
  }))

  return (
    <FigureShell
      figureNumber={1}
      title="Effect of Knowledge Graph Context on Agent Performance"
      emptyMessage={!isLoading && !isError && rows.length === 0
        ? 'No ablation runs found — run scripts/ablation.py' : undefined}
      loading={isLoading}
      error={isError ? 'Failed to load ablation results' : undefined}
      caption="Identical seeds, walk-forward splits and hyperparameters across both arms; the sole difference is whether GraphRAG context is injected into the prediction pipeline."
    >
      {hasSuspicious && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 6, padding: '8px 14px', marginBottom: 16, fontSize: 12, color: '#b91c1c', fontWeight: 600 }}>
          ⚠ Warning: identical arm values detected — verify graph_context reaches the model.
        </div>
      )}

      <ResponsiveContainer width="100%" height={520}>
        <BarChart
          data={chartData}
          margin={{ top: 48, right: 40, left: 20, bottom: 20 }}
          barGap={4}
          barCategoryGap="34%"
        >
          <CartesianGrid strokeDasharray="" vertical={false} stroke="#EAEAEA" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: FONT.tick, fill: '#333' }}
            axisLine={false} tickLine={false}
          />
          <YAxis
            domain={[0, 1.0]}
            tick={{ fontSize: FONT.tick, fill: '#333' }}
            axisLine={false} tickLine={false}
            label={{ value: 'Performance (AUC / R²)', angle: -90, position: 'insideLeft', offset: 16, style: AXIS_STYLE.label }}
          />
          <Tooltip content={<Tip />} />
          {/* Legend top-right, horizontal, no frame */}
          <g />

          <Bar dataKey="with_graph" name="With knowledge graph"
            shape={<WithGraphBar />}
            radius={[3, 3, 0, 0]} {...NO_ANIMATION}>
            <LabelList dataKey="with_graph" content={<ValLabel />} />
          </Bar>

          <Bar dataKey="graph_ablated" name="Graph ablated"
            fill={PALETTE.accent} stroke="#8f3d00" strokeWidth={0.8}
            radius={[3, 3, 0, 0]} {...NO_ANIMATION}>
            <LabelList dataKey="graph_ablated" content={<ValLabel />} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Manual legend top-right */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 20, marginTop: -480, marginBottom: 460, paddingRight: 40, fontSize: FONT.legend }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 14, background: PALETTE.primary, display: 'inline-block', borderRadius: 2 }} />
          With knowledge graph
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 14, background: PALETTE.accent, display: 'inline-block', borderRadius: 2 }} />
          Graph ablated
        </span>
      </div>
    </FigureShell>
  )
}
