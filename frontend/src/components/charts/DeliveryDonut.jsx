import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { ChartTooltip } from './Tooltip'
import EmptyState from '../ui/EmptyState'

const COLORS = ['var(--rl)', 'var(--rm)', 'var(--rh)', 'var(--blue)']

export default function DeliveryDonut({ data = [] }) {
  if (!data.length) return <EmptyState title="No data" />
  return (
    <div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={70}
            dataKey="value" nameKey="name" paddingAngle={2}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
        {data.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--ts)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: COLORS[i % COLORS.length] }} />
            {d.name}: {d.value.toLocaleString()}
          </div>
        ))}
      </div>
    </div>
  )
}
