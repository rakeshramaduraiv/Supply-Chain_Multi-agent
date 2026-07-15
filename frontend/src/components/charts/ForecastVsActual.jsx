import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { ChartTooltip } from './Tooltip'
import EmptyState from '../ui/EmptyState'

export default function ForecastVsActual({ data = [] }) {
  if (!data.length) return <EmptyState title="No comparison data" />
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip content={<ChartTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="monotone" dataKey="forecast" stroke="var(--blue)" strokeWidth={1.5} dot={false} />
        <Line type="monotone" dataKey="actual" stroke="var(--rl)" strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
