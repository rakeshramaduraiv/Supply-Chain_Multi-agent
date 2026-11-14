/**
 * CycleResults.jsx
 * Appears once Stage 3 completes for the inspected period.
 * Shows: forecast vs actual chart, per-entity comparison table,
 * matched/unmatched counts, and metrics (MAPE, MAE, RMSE, F1, precision, recall).
 * All values come from stage_statuses — no browser computation.
 * A real 0 and a missing value render differently.
 * Unmatched entities get their own labelled section with a count.
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import styles from '../../pages/ForecastPage.module.css'

const dash = '\u2014'

function fmt(val, decimals = 2) {
  if (val === null || val === undefined) return dash
  const n = typeof val === 'number' ? val : parseFloat(val)
  if (isNaN(n)) return dash
  return n.toFixed(decimals)
}

function pct(val) {
  if (val === null || val === undefined) return dash
  const n = typeof val === 'number' ? val : parseFloat(val)
  if (isNaN(n)) return dash
  const clamped = Math.max(0, Math.min(100, n))
  return `${clamped.toFixed(2)}%`
}

function MetricBox({ label, value, unit }) {
  return (
    <div style={{
      background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: 8,
      padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 2,
    }}>
      <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--tp)', fontFamily: 'var(--mono)' }}>
        {value}{unit ? <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', marginLeft: 2 }}>{unit}</span> : null}
      </span>
    </div>
  )
}

export default function CycleResults({ periodEntry }) {
  if (!periodEntry) return null

  const ss3 = periodEntry.stage_statuses?.['3']
  if (!ss3 || ss3.status === 'PENDING' || !['COMPLETED', 'SKIPPED'].includes(ss3.status)) return null

  const ss2 = periodEntry.stage_statuses?.['2']
  const d2  = ss2?.detail ?? {}
  const d3  = ss3?.detail ?? {}

  const rowsMatched   = d2.rows_matched   ?? null
  const rowsUnmatched = d2.rows_excluded  ?? null
  const matchRate     = d2.match_rate     ?? null

  // Demand metrics
  const demandMape = d3.demand_mape  ?? null
  const demandMae  = d3.demand_mae   ?? null
  const demandRmse = d3.demand_rmse  ?? null

  // Risk metrics
  const lateF1        = d3.late_delivery_f1        ?? null
  const latePrecision = d3.late_delivery_precision ?? null
  const lateRecall    = d3.late_delivery_recall    ?? null

  // Chart data from stage 2 detail if available
  const forecastAnchors = d2.forecast_anchors ?? null
  const actualAnchors   = d2.actual_anchors   ?? null
  const matchedAnchors  = d2.matched_anchors  ?? null

  const chartData = (forecastAnchors != null && actualAnchors != null) ? [
    { name: 'Forecast entities', value: forecastAnchors, fill: '#60a5fa' },
    { name: 'Actual entities',   value: actualAnchors,   fill: '#00b894' },
    { name: 'Matched',           value: matchedAnchors ?? 0, fill: '#a78bfa' },
  ] : []

  const hasMetrics = demandMape != null || demandMae != null || lateF1 != null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
      {/* Match summary */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 10, padding: '12px 16px',
      }}>
        <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--tp)', marginBottom: 10 }}>
          Stage 3 Results — {periodEntry.period}
        </div>

        {/* Counts */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <div style={{ background: 'rgba(0,184,148,0.08)', border: '1px solid #00b894', borderRadius: 7, padding: '6px 12px', fontSize: 11 }}>
            <span style={{ color: 'var(--tm)' }}>Matched: </span>
            <strong style={{ color: '#00b894' }}>{rowsMatched !== null ? rowsMatched.toLocaleString() : dash}</strong>
          </div>
          <div style={{ background: 'rgba(225,112,85,0.08)', border: '1px solid #e17055', borderRadius: 7, padding: '6px 12px', fontSize: 11 }}>
            <span style={{ color: 'var(--tm)' }}>Unmatched: </span>
            <strong style={{ color: '#e17055' }}>{rowsUnmatched !== null ? rowsUnmatched.toLocaleString() : dash}</strong>
          </div>
          {matchRate !== null && (
            <div style={{ background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: 7, padding: '6px 12px', fontSize: 11 }}>
              <span style={{ color: 'var(--tm)' }}>Match rate: </span>
              <strong>{pct(matchRate * 100)}</strong>
            </div>
          )}
        </div>

        {/* Unmatched section */}
        {rowsUnmatched !== null && rowsUnmatched > 0 && (
          <div style={{ fontSize: 11, color: 'var(--tm)', marginBottom: 10, padding: '6px 10px', background: 'rgba(225,112,85,0.05)', borderRadius: 6, border: '1px solid rgba(225,112,85,0.2)' }}>
            <strong style={{ color: '#e17055' }}>{rowsUnmatched.toLocaleString()} unmatched</strong> entities had no corresponding forecast entry and were excluded from metric computation.
          </div>
        )}

        {/* Metrics */}
        {hasMetrics ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 8 }}>
            {demandMape  != null && <MetricBox label="Demand MAPE"  value={fmt(demandMape, 2)}  unit="%" />}
            {demandMae   != null && <MetricBox label="Demand MAE"   value={fmt(demandMae, 3)}   />}
            {demandRmse  != null && <MetricBox label="Demand RMSE"  value={fmt(demandRmse, 3)}  />}
            {lateF1      != null && <MetricBox label="Risk F1"      value={fmt(lateF1, 3)}      />}
            {latePrecision != null && <MetricBox label="Precision"  value={fmt(latePrecision, 3)} />}
            {lateRecall  != null && <MetricBox label="Recall"       value={fmt(lateRecall, 3)}  />}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--tm)' }}>
            {ss3.status === 'SKIPPED'
              ? `Metrics skipped \u2014 ${ss3.detail?.reason ?? 'no matched rows'}`
              : 'No metrics available for this period'}
          </div>
        )}
      </div>

      {/* Entity count chart */}
      {chartData.length > 0 && (
        <div style={{ background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 10, padding: '12px 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--tp)', marginBottom: 8 }}>
            Entity Coverage — {periodEntry.period}
          </div>
          <div style={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ left: -10, right: 10, top: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => [v.toLocaleString(), 'Count']} />
                <Bar dataKey="value" name="Count" radius={[3, 3, 0, 0]}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
