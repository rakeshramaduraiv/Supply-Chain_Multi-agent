// src/components/figures/Fig2TPKETimeline.jsx
import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT, NO_ANIMATION, AXIS_STYLE } from './figureTheme'

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '9px 13px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)' }}>
      <div style={{ fontWeight: 700, marginBottom: 5 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: p.color, marginBottom: 2 }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 600 }}>{Number(p.value).toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

// Custom dot for the cumulative line
const CumDot = (props) => {
  const { cx, cy, stroke } = props
  return <circle cx={cx} cy={cy} r={7} fill="#fff" stroke={stroke} strokeWidth={1.4} />
}

// Label above each cumulative dot
const CumLabel = ({ x, y, value }) => (
  <text x={x} y={y - 12} textAnchor="middle" fontSize={10.5} fill={PALETTE.primary}>
    {Number(value).toLocaleString()}
  </text>
)

export default function Fig2TPKETimeline() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'tpke-timeline'],
    queryFn: () => api.getTpkeEvolutionTimeline().then(r => r.data),
    staleTime: 60_000, retry: 2,
  })

  const timeline = data?.timeline || []
  const injected = data?.injected_events || []

  const maxCum     = timeline.length ? Math.max(...timeline.map(r => r.cumulative_edges)) : 1
  const maxCreated = timeline.length ? Math.max(...timeline.map(r => r.edges_created))    : 1

  return (
    <FigureShell
      figureNumber={2}
      title="TPKE Knowledge Graph Evolution Timeline"
      subtitle="TPKE parameters frozen a priori:  θ = 0.70,  K = 3,  δ = 0.05,  θ_rem = 0.10"
      emptyMessage={!isLoading && !isError && timeline.length === 0
        ? 'No TPKE evolution logged — run scripts/run_drift_experiment.py' : undefined}
      loading={isLoading}
      error={isError ? 'Failed to load TPKE timeline' : undefined}
      caption="Supplier degradation injected at 2018-04. TPKE edge creation responds within the same window, with no prior knowledge of the injection manifest."
    >
      <ResponsiveContainer width="100%" height={540}>
        <ComposedChart data={timeline} margin={{ top: 40, right: 80, left: 20, bottom: 40 }}>
          <CartesianGrid strokeDasharray="" vertical={false} stroke={PALETTE.gridline} />

          <XAxis
            dataKey="month"
            tick={{ fontSize: FONT.tick, fill: PALETTE.primary }}
            axisLine={false} tickLine={false}
            label={{ value: 'Continuation month', position: 'insideBottom', offset: -20, style: AXIS_STYLE.label }}
          />

          {/* LEFT: cumulative edges */}
          <YAxis
            yAxisId="left"
            domain={[0, maxCum * 1.30]}
            tick={{ fontSize: FONT.tick, fill: PALETTE.primary }}
            axisLine={false} tickLine={false}
            label={{ value: 'Cumulative graph edges', angle: -90, position: 'insideLeft', offset: 16, style: { fontSize: FONT.axisLabel, fill: PALETTE.primary } }}
          />

          {/* RIGHT: edges created */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, maxCreated * 1.55]}
            tick={{ fontSize: FONT.tick, fill: PALETTE.green }}
            axisLine={false} tickLine={false}
            label={{ value: 'Edges created in month', angle: 90, position: 'insideRight', offset: 16, style: { fontSize: FONT.axisLabel, fill: PALETTE.green } }}
          />

          <Tooltip content={<Tip />} />

          {/* Injected event reference lines */}
          {injected.map((ev, i) => (
            <ReferenceLine
              key={i} yAxisId="left" x={ev.month}
              stroke={PALETTE.accent} strokeDasharray="6 3" strokeWidth={2}
              label={{
                value: `Injected:\n${ev.event_type || ev.event || ''}`,
                position: 'insideTopRight',
                fontSize: 11.5, fontWeight: 'bold', fill: PALETTE.accent,
              }}
            />
          ))}

          {/* Bars: edges created per month */}
          <Bar
            yAxisId="right"
            dataKey="edges_created"
            name="Edges created in month"
            fill={PALETTE.green}
            fillOpacity={0.75}
            stroke="#00614a"
            strokeWidth={0.8}
            barSize={28}
            radius={[3, 3, 0, 0]}
            {...NO_ANIMATION}
          />

          {/* Step line: cumulative edges */}
          <Line
            yAxisId="left"
            type="step"
            dataKey="cumulative_edges"
            name="Cumulative graph edges"
            stroke={PALETTE.primary}
            strokeWidth={2.6}
            dot={<CumDot stroke={PALETTE.primary} />}
            label={<CumLabel />}
            {...NO_ANIMATION}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Manual legend top-left */}
      <div style={{ display: 'flex', gap: 20, marginTop: -560, marginBottom: 540, paddingLeft: 60, fontSize: FONT.legend }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 24, height: 3, background: PALETTE.primary, display: 'inline-block' }} />
          Cumulative graph edges
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 14, background: PALETTE.green, display: 'inline-block', borderRadius: 2, opacity: 0.75 }} />
          Edges created in month
        </span>
      </div>
    </FigureShell>
  )
}
