import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { ChartTooltip } from './Tooltip'
import EmptyState from '../ui/EmptyState'

export default function RiskTrend({ data = [] }) {
  if (!data.length) return <EmptyState title="No trend data" />
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
        <Tooltip content={<ChartTooltip fmt={v => `${(v * 100).toFixed(1)}%`} />} />
        <ReferenceLine y={0.65} stroke="var(--rh)" strokeDasharray="4 4" label={{ value: 'High', fill: 'var(--tm)', fontSize: 9 }} />
        <ReferenceLine y={0.35} stroke="var(--rm)" strokeDasharray="4 4" label={{ value: 'Med', fill: 'var(--tm)', fontSize: 9 }} />
        <Area type="monotone" dataKey="combined" stroke="var(--rh)" strokeWidth={1.5}
          fill="rgba(229,83,75,.12)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
