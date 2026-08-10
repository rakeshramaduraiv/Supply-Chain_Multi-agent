/**
 * ForecastCharts.jsx — Historical vs Forecast + Confidence Timeline charts
 */
import { Activity, ShieldCheck } from 'lucide-react'
import {
  ComposedChart, LineChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--b)',
      borderRadius: 8, padding: '8px 12px', fontSize: 11,
      boxShadow: '0 4px 16px rgba(0,0,0,.25)',
    }}>
      <div style={{ fontWeight: 600, color: 'var(--tp)', marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color || p.stroke, flexShrink: 0 }} />
          <span style={{ color: 'var(--ts)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--tp)', fontVariantNumeric: 'tabular-nums' }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function ForecastCharts({ historicalForecastSeries, confidenceTimeline, cycleMonth }) {
  return (
    <div id="forecast-chart-anchor" className="g2">
      <div className="card" style={{ padding: '16px' }}>
        <div className="card-head" style={{ marginBottom: '12px' }}>
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={15} style={{ color: 'var(--blue)' }} />
            Historical Orders vs Model Predictions — Forecast: {cycleMonth}
          </span>
        </div>
        <div style={{ height: '220px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={historicalForecastSeries} margin={{ left: -15, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
              <XAxis dataKey="period" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 9 }} />
              <Bar dataKey="historical" name="Historical Orders" fill="var(--blue)" barSize={16} radius={[3, 3, 0, 0]} />
              <Line type="monotone" dataKey="forecast" name="Predicted Forecast" stroke="#00b894" strokeWidth={2.5} dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ padding: '16px' }}>
        <div className="card-head" style={{ marginBottom: '12px' }}>
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={15} style={{ color: '#00b894' }} />
            Prediction Confidence Timeline Across Cycles (%)
          </span>
        </div>
        <div style={{ height: '220px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={confidenceTimeline} margin={{ left: -15, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} domain={[70, 100]} unit="%" />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 9 }} />
              <Line type="monotone" dataKey="prediction_confidence" name="Prediction Confidence %" stroke="var(--blue)" strokeWidth={2} />
              <Line type="monotone" dataKey="validation_confidence" name="Validation Confidence %" stroke="#00b894" strokeWidth={2} strokeDasharray="3 3" />
              <Line type="monotone" dataKey="rolling_average" name="Rolling Avg Confidence" stroke="#7c6fcd" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
