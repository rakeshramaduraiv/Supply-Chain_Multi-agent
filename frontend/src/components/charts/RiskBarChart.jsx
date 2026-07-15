import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { ChartTooltip } from './Tooltip'
import EmptyState from '../ui/EmptyState'

export default function RiskBarChart({ data = [], dataKey = 'value', nameKey = 'name', referenceLine }) {
  if (!data.length) return <EmptyState title="No data" />
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout="vertical" margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`} />
        <YAxis type="category" dataKey={nameKey} width={100} tick={{ fontSize: 11 }} />
        <Tooltip content={<ChartTooltip fmt={v => `${v.toFixed(1)}%`} />} />
        {referenceLine && <ReferenceLine x={referenceLine} stroke="var(--tm)" strokeDasharray="4 4" />}
        <Bar dataKey={dataKey} radius={[0, 3, 3, 0]} barSize={14}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.value >= 65 ? 'var(--rh)' : d.value >= 40 ? 'var(--rm)' : 'var(--rl)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
