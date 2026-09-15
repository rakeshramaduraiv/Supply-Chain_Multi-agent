// src/components/figures/Fig7DatasetOverview.jsx
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { COLORS, PALETTE, AXIS_STYLE, NO_ANIMATION } from './figureTheme'

const PIE_COLORS = ['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00','#56B4E9','#F0E442','#999999','#000000']

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '9px 13px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)' }}>
      <div style={{ fontWeight: 700, marginBottom: 5 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: p.color || '#94a3b8', marginBottom: 2 }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 600 }}>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  )
}

const StatCard = ({ label, value, sub, color = '#0072B2' }) => (
  <div style={{ flex: '1 1 140px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 16px', boxShadow: '0 1px 3px rgba(0,0,0,.04)' }}>
    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    <div style={{ fontSize: 12, color: '#475569', marginTop: 2, fontWeight: 500 }}>{label}</div>
    {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>{sub}</div>}
  </div>
)

const SectionTitle = ({ children }) => (
  <div style={{ fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 12, marginTop: 24, paddingBottom: 6, borderBottom: '1px solid #f1f5f9' }}>
    {children}
  </div>
)

export default function Fig7DatasetOverview() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'dataset-overview'],
    queryFn: () => api.getDatasetOverview().then(r => r.data),
    staleTime: 300_000, retry: 2,
  })

  const empty = !isLoading && !isError && (!data || !data.total_orders)
    ? 'Dataset not loaded — run initialization' : false

  return (
    <FigureShell
      figureNumber={7}
      title="DataCo Smart Supply Chain — Dataset Overview"
      caption="DataCo Smart Supply Chain training window (Jan 2015 – Sep 2017). Source: DataCo Global Supply Chain dataset."
      loading={isLoading} error={isError ? 'Failed to load dataset overview' : false}
      empty={empty} dataPoints={data?.total_orders || null}
    >
      {/* KPI row */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
        <StatCard label="Total Orders"     value={data?.total_orders?.toLocaleString()}  sub={`${data?.date_range?.start?.slice(0,7)} – ${data?.date_range?.end?.slice(0,7)}`} color={COLORS.blue}   />
        <StatCard label="Late Delivery"    value={`${(data?.overall_late_rate * 100).toFixed(1)}%`} sub="of all orders"  color={COLORS.orange} />
        <StatCard label="Markets"          value="5"                                      sub="LATAM · Europe · Asia · USCA · Africa" color={COLORS.green}  />
        <StatCard label="Shipping Modes"   value="4"                                      sub="Standard · Second · First · Same Day"  color={COLORS.pink}   />
        <StatCard label="Date Range"       value={`${data?.date_range?.start?.slice(0,7)} → ${data?.date_range?.end?.slice(0,7)}`} sub="Training window" color="#64748b" />
      </div>

      {/* Monthly volume + late rate */}
      <SectionTitle>Monthly Order Volume & Late Delivery Rate</SectionTitle>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data?.monthly_volume || []} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={COLORS.blue} stopOpacity={0.25} />
              <stop offset="95%" stopColor={COLORS.blue} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false}
            tickFormatter={v => v.slice(2)} interval={3} />
          <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <YAxis yAxisId="right" orientation="right" domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`}
            tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Area yAxisId="left" type="monotone" dataKey="orders" name="Orders" stroke={COLORS.blue} strokeWidth={2}
            fill="url(#volGrad)" dot={false} {...NO_ANIMATION} />
          <Area yAxisId="right" type="monotone" dataKey="late_rate" name="Late Rate" stroke={COLORS.orange}
            strokeWidth={1.5} fill="none" dot={false} strokeDasharray="4 2" {...NO_ANIMATION} />
        </AreaChart>
      </ResponsiveContainer>

      {/* Market + Shipping side by side */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 4 }}>
        {/* Market breakdown */}
        <div style={{ flex: '1 1 300px' }}>
          <SectionTitle>Orders by Market</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data?.market_breakdown || []} layout="vertical" margin={{ top: 0, right: 60, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="Market" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} width={90} />
              <Tooltip content={<Tip />} />
              <Bar dataKey="orders" name="Orders" radius={[0,4,4,0]} {...NO_ANIMATION}>
                {(data?.market_breakdown || []).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Shipping mode */}
        <div style={{ flex: '1 1 300px' }}>
          <SectionTitle>Shipping Mode Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data?.shipping_mode_breakdown || []} layout="vertical" margin={{ top: 0, right: 80, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="Shipping Mode" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} width={100} />
              <Tooltip content={<Tip />} />
              <Bar dataKey="orders" name="Orders" radius={[0,4,4,0]} {...NO_ANIMATION}>
                {(data?.shipping_mode_breakdown || []).map((_, i) => <Cell key={i} fill={PALETTE[(i+2) % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Late rate by market + shipping */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 4 }}>
        <div style={{ flex: '1 1 300px' }}>
          <SectionTitle>Late Delivery Rate by Market</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data?.market_breakdown || []} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="Market" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
              <ReferenceLine y={data?.overall_late_rate || 0} stroke="#94a3b8" strokeDasharray="4 2"
                label={{ value: 'avg', position: 'right', fontSize: 10, fill: '#94a3b8' }} />
              <Bar dataKey="late_rate" name="Late Rate" radius={[4,4,0,0]} {...NO_ANIMATION}>
                {(data?.market_breakdown || []).map((r, i) => (
                  <Cell key={i} fill={(r.late_rate || 0) > (data?.overall_late_rate || 0) ? COLORS.orange : COLORS.blue} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Order status pie */}
        <div style={{ flex: '1 1 280px' }}>
          <SectionTitle>Order Status Distribution</SectionTitle>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <PieChart width={160} height={160}>
              <Pie data={data?.order_status || []} dataKey="count" nameKey="status"
                cx={75} cy={75} innerRadius={40} outerRadius={72} paddingAngle={2} isAnimationActive={false}>
                {(data?.order_status || []).map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={v => v.toLocaleString()} />
            </PieChart>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {(data?.order_status || []).map((r, i) => (
                <div key={r.status} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                  <span style={{ color: '#475569' }}>{r.status}</span>
                  <span style={{ color: '#94a3b8', marginLeft: 'auto' }}>{r.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Top categories */}
      <SectionTitle>Top 10 Categories by Order Volume</SectionTitle>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data?.top_categories || []} margin={{ top: 5, right: 60, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="Category Name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false}
            angle={-20} textAnchor="end" height={40} />
          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <YAxis yAxisId="right" orientation="right" domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}%`}
            tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="orders" name="Orders" fill={COLORS.blue} radius={[3,3,0,0]} {...NO_ANIMATION} />
          <Bar yAxisId="right" dataKey="late_rate" name="Late Rate" fill={COLORS.orange} fillOpacity={0.6} radius={[3,3,0,0]} {...NO_ANIMATION} />
        </BarChart>
      </ResponsiveContainer>
    </FigureShell>
  )
}
