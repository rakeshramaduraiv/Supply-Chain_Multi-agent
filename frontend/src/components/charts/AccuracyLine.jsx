import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { ChartTooltip } from './Tooltip'
import EmptyState from '../ui/EmptyState'

export default function AccuracyLine({ data = [] }) {
  if (!data.length) return <EmptyState title="No accuracy data" />
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
        <Tooltip content={<ChartTooltip fmt={v => `${v.toFixed(1)}%`} />} />
        <Line type="monotone" dataKey="accuracy" stroke="var(--rl)" strokeWidth={1.5} dot={{ r: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
