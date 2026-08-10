// src/components/figures/Fig5WalkForward.jsx
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { useMemo } from 'react'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT, NO_ANIMATION, AXIS_STYLE } from './figureTheme'

const AGENT_COLORS = {
  Logistics: PALETTE.green,
  Supplier:  PALETTE.primary,
  Demand:    PALETTE.pink,
}

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)' }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{label}</div>
      {payload.map(p => p.value != null && (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 20, marginBottom: 2, color: p.color }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 700 }}>{Number(p.value).toFixed(4)}</span>
        </div>
      ))}
    </div>
  )
}

// Custom dot: circle with white stroke
const AgentDot = ({ cx, cy, stroke }) => (
  <circle cx={cx} cy={cy} r={6.5} fill={stroke} stroke="#fff" strokeWidth={1.2} />
)

export default function Fig5WalkForward() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'walk-forward'],
    queryFn: () => api.getWalkForwardHistory().then(r => r.data),
    staleTime: 120_000, retry: 2,
  })

  const agents = Array.isArray(data) ? data : []

  const { chartData, agentKeys } = useMemo(() => {
    const map = {}
    const keys = []
    agents.forEach(ag => {
      const key   = ag.agent
      const color = AGENT_COLORS[ag.agent] || PALETTE.grey
      keys.push({ key, label: `${ag.agent} (${ag.metric_name})`, color, mean: ag.mean, std: ag.std })
      ag.folds.forEach(f => {
        const period = f.test_period || `Fold ${f.fold_index}`
        if (!map[period]) map[period] = { period }
        map[period][key] = f.metric_value
      })
    })
    return {
      chartData: Object.values(map).sort((a, b) => a.period.localeCompare(b.period)),
      agentKeys: keys,
    }
  }, [agents])

  return (
    <FigureShell
      figureNumber={5}
      title="Walk-Forward Validation Performance"
      emptyMessage={!isLoading && !isError && agents.length === 0
        ? 'No per-fold results persisted — update the walk-forward validation routine to persist fold output.' : undefined}
      loading={isLoading}
      error={isError ? 'Failed to load walk-forward history' : undefined}
      caption="Each point is a model trained exclusively on periods preceding its test window. Dashed lines mark the mean across folds. No future information enters training."
    >
      {/* Legend top-left, horizontal, no frame */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 12, fontSize: FONT.legend }}>
        {agentKeys.map(ag => (
          <span key={ag.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 24, height: 3, background: ag.color, display: 'inline-block', borderRadius: 2 }} />
            {ag.label}
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={500}>
        <LineChart data={chartData} margin={{ top: 20, right: 80, left: 20, bottom: 50 }}>
          <CartesianGrid strokeDasharray="" vertical={false} stroke={PALETTE.gridline} />
          <XAxis
            dataKey="period"
            tick={{ fontSize: FONT.tick, fill: '#333' }}
            axisLine={false} tickLine={false}
            label={{ value: 'Test period (walk-forward fold)', position: 'insideBottom', offset: -24, style: AXIS_STYLE.label }}
          />
          <YAxis
            domain={[0.4, 1.0]}
            tick={{ fontSize: FONT.tick, fill: '#333' }}
            axisLine={false} tickLine={false}
            label={{ value: 'Performance (AUC / R²)', angle: -90, position: 'insideLeft', offset: 16, style: AXIS_STYLE.label }}
          />
          <Tooltip content={<Tip />} />

          {/* Mean reference lines */}
          {agentKeys.map(ag => (
            <ReferenceLine
              key={`m-${ag.key}`}
              y={ag.mean}
              stroke={ag.color}
              strokeDasharray="6 3"
              strokeOpacity={0.45}
              label={{ value: `mean ${ag.mean.toFixed(2)}`, position: 'right', fontSize: 10.5, fill: ag.color }}
            />
          ))}

          {/* Agent lines */}
          {agentKeys.map(ag => (
            <Line
              key={ag.key}
              dataKey={ag.key}
              name={ag.label}
              stroke={ag.color}
              strokeWidth={2.1}
              dot={<AgentDot stroke={ag.color} />}
              connectNulls
              {...NO_ANIMATION}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </FigureShell>
  )
}
