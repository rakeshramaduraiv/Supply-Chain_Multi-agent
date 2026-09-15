/**
 * CycleHistoryPanel.jsx
 *
 * Cycle-history view: one row per cycle showing month, matched pairs,
 * each metric, and TPKE mutation counts.
 *
 * Metrics that are None/empty because a stage was SKIPPED render as an
 * em dash (—) with tooltip "no matched pairs in this cycle".
 * Never renders 0 for a skipped metric.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { History } from 'lucide-react'
import EmptyState from '../ui/EmptyState'

const SKIPPED_TOOLTIP = 'no matched pairs in this cycle'

function MetricCell({ value }) {
  if (value === null || value === undefined || value === '') {
    return (
      <td
        title={SKIPPED_TOOLTIP}
        style={{ padding: '6px 8px', color: 'var(--tm)', textAlign: 'right', cursor: 'help' }}
      >
        —
      </td>
    )
  }
  const num = typeof value === 'number' ? value : parseFloat(value)
  return (
    <td style={{ padding: '6px 8px', fontVariantNumeric: 'tabular-nums', textAlign: 'right', color: 'var(--tp)' }}>
      {isNaN(num) ? '—' : num.toFixed(3)}
    </td>
  )
}

// Inline sparkline for TPKE edge counts across cycles
function TpkeSparkline({ data }) {
  if (!data || data.length < 2) return null
  const vals = data.map(d => d.total_inferred_edges ?? 0)
  const max = Math.max(...vals, 1)
  const W = 80
  const H = 24
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * W
    const y = H - (v / max) * H
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width={W} height={H} style={{ display: 'block' }}>
      <polyline
        points={pts}
        fill="none"
        stroke="var(--blue)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {vals.map((v, i) => {
        const x = (i / (vals.length - 1)) * W
        const y = H - (v / max) * H
        return <circle key={i} cx={x} cy={y} r={2.5} fill="var(--blue)" />
      })}
    </svg>
  )
}

export default function CycleHistoryPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cycleHistory'],
    queryFn: () => api.getCycleHistory().then(r => r.data),
    staleTime: 30_000,
  })

  const cycles = data?.cycles || []

  if (isLoading) {
    return <div style={{ padding: 20, fontSize: 11, color: 'var(--tm)' }}>Loading cycle history…</div>
  }

  if (isError || cycles.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No cycle history"
        desc="Run replay_holdout.py or upload actuals to populate cycle history."
      />
    )
  }

  const tpkeSparkData = cycles.map(c => ({
    month: c.month,
    total_inferred_edges: c.total_inferred_edges ?? 0,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* TPKE edge-count sparkline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--ts)' }}>TPKE edges across cycles</span>
        <TpkeSparkline data={tpkeSparkData} />
        <span style={{ fontSize: 10, color: 'var(--tm)' }}>
          {tpkeSparkData.map(d => `${d.month}: ${d.total_inferred_edges}`).join(' · ')}
        </span>
      </div>

      {/* Cycle history table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--b)', color: 'var(--tm)', textAlign: 'left' }}>
              <th style={{ padding: '6px 8px' }}>Month</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Rows</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Matched</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Dem MAE</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Dem R²</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Sup AUC</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Sup F1</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Log AUC</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Log F1</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>TPKE+</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>TPKE~</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>TPKE tot</th>
              <th style={{ padding: '6px 8px' }}>Stage 3</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((c, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--b)', color: 'var(--tp)' }}>
                <td style={{ padding: '6px 8px', fontWeight: 700, color: 'var(--blue)' }}>{c.month}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{c.rows_uploaded?.toLocaleString() ?? '—'}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  {c.matched_pairs === '' || c.matched_pairs == null
                    ? <span title={SKIPPED_TOOLTIP} style={{ color: 'var(--tm)', cursor: 'help' }}>—</span>
                    : c.matched_pairs}
                </td>
                <MetricCell value={c.demand_mae} />
                <MetricCell value={c.demand_r2} />
                <MetricCell value={c.supplier_auc} />
                <MetricCell value={c.supplier_f1} />
                <MetricCell value={c.logistics_auc} />
                <MetricCell value={c.logistics_f1} />
                <td style={{ padding: '6px 8px', textAlign: 'right', color: '#00b894' }}>{c.tpke_edges_created ?? 0}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', color: '#f59e0b' }}>{c.tpke_edges_strengthened ?? 0}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--blue)' }}>{c.total_inferred_edges ?? 0}</td>
                <td style={{ padding: '6px 8px' }}>
                  <span className={`badge ${c.stage3_status === 'SKIPPED' ? 'bdg-med' : c.stage3_status === 'COMPLETED' ? 'bdg-low' : 'bdg-high'}`}>
                    {c.stage3_status || '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {cycles.some(c => c.stage3_status === 'SKIPPED') && (
        <div style={{ fontSize: 10, color: 'var(--tm)', fontStyle: 'italic' }}>
          — = no matched pairs in this cycle (stage SKIPPED). Measurement begins at cycle 2.
        </div>
      )}
    </div>
  )
}
