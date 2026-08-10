// src/components/figures/Fig6LeakageCorrection.jsx
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, LabelList, ResponsiveContainer,
} from 'recharts'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT, NO_ANIMATION, AXIS_STYLE } from './figureTheme'

const AGENT_LABELS = {
  Demand:    'Demand  (R²)',
  Supplier:  'Supplier  (AUC)',
  Logistics: 'Logistics  (AUC)',
}

const ValLabel = ({ x, y, width, value }) => {
  if (value == null) return null
  return (
    <text x={x + width / 2} y={y - 5} textAnchor="middle"
      fontSize={FONT.footnote} fill="#222">
      {Number(value).toFixed(2)}
    </text>
  )
}

// "not sourced" italic grey text at the before-bar slot
const NotSourcedLabel = ({ x, y, width }) => (
  <text x={x + width / 2} y={y + 20} textAnchor="middle"
    fontSize={9.5} fontStyle="italic" fill={PALETTE.grey}>
    not
  </text>
)

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)', maxWidth: 240 }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{label}</div>
      {payload.map(p => p.value != null && (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 20, marginBottom: 3, color: p.color }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 700 }}>{Number(p.value).toFixed(4)}</span>
        </div>
      ))}
      {d?.before != null && d?.after != null && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,.1)', color: '#f87171', fontWeight: 600 }}>
          Drop: −{(d.before - d.after).toFixed(4)} ({((d.before - d.after) / d.before * 100).toFixed(1)}%)
        </div>
      )}
    </div>
  )
}

// Custom tick that renders removed features below the agent label
function FeatureTick({ x, y, payload, removedMap }) {
  const feats = removedMap[payload.value] || []
  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" fontSize={FONT.tick} fill="#333" dy={12}>{payload.value}</text>
      {feats.slice(0, 4).map((f, i) => (
        <text key={f} textAnchor="middle" fontSize={9} fontFamily="monospace"
          fill={PALETTE.grey} dy={28 + i * 13}>{f}</text>
      ))}
      {feats.length > 4 && (
        <text textAnchor="middle" fontSize={9} fill="#94a3b8" dy={28 + 4 * 13}>
          +{feats.length - 4} more
        </text>
      )}
    </g>
  )
}

export default function Fig6LeakageCorrection() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'metrics-history'],
    queryFn: () => api.getMetricsHistory().then(r => r.data),
    staleTime: 120_000, retry: 2,
  })

  const rows = Array.isArray(data) ? data : []

  const chartData = rows.map(r => ({
    agent:   AGENT_LABELS[r.agent] || r.agent,
    agentRaw: r.agent,
    before:  r.before,
    after:   r.after,
    removed: r.removed_features || [],
    metric:  r.metric_name,
  }))

  // Map agent label -> removed features for custom tick
  const removedMap = {}
  chartData.forEach(r => { removedMap[r.agent] = r.removed })

  // Find Demand row for curved arrow
  const demandRow = chartData.find(r => r.agentRaw === 'Demand')

  return (
    <FigureShell
      figureNumber={6}
      title="Effect of Target Leakage Removal on Reported Metrics"
      emptyMessage={!isLoading && !isError && rows.length === 0
        ? 'metrics_history.json not found.' : undefined}
      loading={isLoading}
      error={isError ? 'Failed to load metrics history' : undefined}
      caption="Metrics after removing post-shipment and algebraic target leakage. The lower corrected values are the ones reported throughout this work."
    >
      {/* Legend top-right, no frame */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 20, marginBottom: 12, fontSize: FONT.legend }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 14, background: PALETTE.accent, opacity: 0.55, display: 'inline-block', borderRadius: 2 }} />
          Before leakage removal
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 14, background: PALETTE.primary, display: 'inline-block', borderRadius: 2 }} />
          After leakage removal
        </span>
      </div>

      <div style={{ display: 'flex', gap: 24 }}>
        {/* Bar chart — extra bottom margin for feature labels */}
        <div style={{ flex: '1 1 700px', position: 'relative' }}>
          <ResponsiveContainer width="100%" height={480}>
            <BarChart
              data={chartData}
              margin={{ top: 30, right: 20, left: 20, bottom: 120 }}
              barGap={4}
              barCategoryGap="32%"
            >
              <CartesianGrid strokeDasharray="" vertical={false} stroke={PALETTE.gridline} />
              <XAxis
                dataKey="agent"
                tick={<FeatureTick removedMap={removedMap} />}
                axisLine={false} tickLine={false}
                interval={0}
                height={120}
              />
              <YAxis
                domain={[0, 1.05]}
                tick={{ fontSize: FONT.tick, fill: '#333' }}
                axisLine={false} tickLine={false}
                label={{ value: 'Reported performance', angle: -90, position: 'insideLeft', offset: 16, style: AXIS_STYLE.label }}
              />
              <Tooltip content={<Tip />} />

              {/* Before bar — transparent when null */}
              <Bar dataKey="before" name="Before leakage removal"
                radius={[4, 4, 0, 0]} {...NO_ANIMATION}>
                {chartData.map((r, i) => (
                  <Cell key={i}
                    fill={r.before != null ? PALETTE.accent : 'transparent'}
                    fillOpacity={r.before != null ? 0.55 : 0}
                    stroke={r.before != null ? '#8f3d00' : 'none'}
                    strokeWidth={0.8}
                  />
                ))}
                <LabelList dataKey="before" content={<ValLabel />} />
              </Bar>

              {/* After bar */}
              <Bar dataKey="after" name="After leakage removal"
                fill={PALETTE.primary} stroke="#00456e" strokeWidth={0.8}
                radius={[4, 4, 0, 0]} {...NO_ANIMATION}>
                <LabelList dataKey="after" content={<ValLabel />} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* "not sourced" italic text for null before values */}
          {chartData.filter(r => r.before == null).map(r => (
            <div key={r.agent} style={{ position: 'absolute', fontSize: 9.5, fontStyle: 'italic', color: PALETTE.grey, top: 200, left: '20%' }}>
              not<br />sourced
            </div>
          ))}

          {/* Curved arrow for Demand pair */}
          {demandRow?.before != null && demandRow?.after != null && (
            <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 480, pointerEvents: 'none' }}>
              <defs>
                <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                  <polygon points="0 0, 8 3, 0 6" fill="#333" />
                </marker>
              </defs>
              {/* Approximate positions for Demand bars — first group */}
              <path
                d="M 195 95 Q 215 60 235 95"
                fill="none" stroke="#333" strokeWidth={1.7}
                markerEnd="url(#arrowhead)"
              />
              <text x={215} y={52} textAnchor="middle" fontSize={12.5} fontWeight="bold" fill="#333">
                −{(demandRow.before - demandRow.after).toFixed(2)}
              </text>
            </svg>
          )}
        </div>

        {/* Removed features panel */}
        <div style={{ flex: '0 0 280px', display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 30 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Removed leaky features</div>
          {chartData.map(r => (
            <div key={r.agent} style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#991b1b', marginBottom: 6 }}>{r.agentRaw}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {r.removed.map(f => (
                  <span key={f} style={{ fontSize: 9, fontFamily: 'monospace', background: '#fff', color: '#b91c1c', border: '1px solid #fca5a5', borderRadius: 4, padding: '2px 5px' }}>{f}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </FigureShell>
  )
}
