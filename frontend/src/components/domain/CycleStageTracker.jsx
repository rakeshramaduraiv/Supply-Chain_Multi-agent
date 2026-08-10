/**
 * CycleStageTracker.jsx
 *
 * Displays live 6-stage cycle progress from useCycleStream.
 * Shows EmptyState when no cycle is active.
 * Zero fabricated values — all data from WebSocket events.
 */

import { Layers, CheckCircle, Clock, AlertTriangle, Loader } from 'lucide-react'
import EmptyState from '../ui/EmptyState'

const STAGE_NAMES = {
  1: 'Ingest & Validate',
  2: 'Match Forecast vs Actual',
  3: 'Compute Metrics',
  4: 'TPKE Evolution',
  5: 'Store & Retrain',
  6: 'Forecast Next Period',
}

const STATUS_COLOR = {
  COMPLETED: '#00b894',
  SKIPPED:   '#f59e0b',
  FAILED:    '#d63031',
  RUNNING:   'var(--blue)',
}

function StageCard({ num, event }) {
  const name   = STAGE_NAMES[num] || `Stage ${num}`
  const status = event?.status || 'WAITING'
  const color  = STATUS_COLOR[status] || 'var(--tm)'
  const pct    = status === 'COMPLETED' || status === 'SKIPPED' ? '100%'
               : status === 'RUNNING'   ? '50%' : '0%'

  return (
    <div style={{
      background: status === 'COMPLETED' ? 'rgba(0,184,148,0.04)'
                : status === 'RUNNING'   ? 'rgba(59,130,246,0.06)'
                : 'var(--s0)',
      border: `1px solid ${status === 'COMPLETED' ? 'rgba(0,184,148,0.3)'
             : status === 'RUNNING' ? 'var(--blue)' : 'var(--b)'}`,
      borderRadius: 8, padding: '10px 12px',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 10, fontWeight: 800, color: 'var(--tm)' }}>STAGE {num}</span>
        <span className={`badge ${status === 'COMPLETED' ? 'bdg-low' : status === 'RUNNING' ? 'bdg-blue' : status === 'FAILED' ? 'bdg-high' : 'bdg-med'}`}>
          {status === 'RUNNING' ? <><Loader size={9} style={{ marginRight: 3 }} />{status}</> : status}
        </span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--tp)' }}>{name}</div>
      {event?.duration_ms != null && (
        <div style={{ fontSize: 10, color: 'var(--tm)' }}>
          {(event.duration_ms / 1000).toFixed(2)}s
        </div>
      )}
      <div style={{ width: '100%', height: 4, background: 'var(--b)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: pct, background: color, transition: 'width 0.3s ease' }} />
      </div>
      {event?.detail && Object.keys(event.detail).length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--ts)', lineHeight: 1.4 }}>
          {Object.entries(event.detail)
            .filter(([, v]) => v != null && v !== '')
            .slice(0, 3)
            .map(([k, v]) => (
              <span key={k} style={{ marginRight: 8 }}>
                {k.replace(/_/g, ' ')}: <strong>{typeof v === 'number' ? v.toLocaleString() : String(v)}</strong>
              </span>
            ))}
        </div>
      )}
      {event?.error && (
        <div style={{ fontSize: 10, color: '#d63031' }}>
          <AlertTriangle size={10} style={{ marginRight: 3 }} />{event.error}
        </div>
      )}
    </div>
  )
}

export default function CycleStageTracker({ cycleId, stages, complete, connected, period }) {
  const hasActivity = cycleId || Object.keys(stages || {}).length > 0

  if (!hasActivity) {
    return (
      <EmptyState
        icon={Layers}
        title="No active cycle"
        description={`Upload actuals for ${period || 'the current period'} to start the 6-stage pipeline.`}
      />
    )
  }

  const completedCount = Object.values(stages || {}).filter(e => e.status === 'COMPLETED' || e.status === 'SKIPPED').length

  return (
    <div style={{ background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 12, padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--tp)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={18} style={{ color: 'var(--blue)' }} />
          6-Stage Upload Cycle Pipeline {period ? `(${period})` : ''}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: connected ? '#00b894' : 'var(--tm)', fontWeight: 700 }}>
            {connected ? '● Live' : '○ Reconnecting'}
          </span>
          <span className="badge bdg-blue">
            {complete ? 'Complete' : `Stage ${completedCount}/6`}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
        {[1, 2, 3, 4, 5, 6].map(n => (
          <StageCard key={n} num={n} event={stages?.[n]} />
        ))}
      </div>

      {complete && (
        <div style={{ borderTop: '1px solid var(--b)', paddingTop: 10, fontSize: 11, color: '#00b894', fontWeight: 700, display: 'flex', gap: 16 }}>
          <span><CheckCircle size={12} style={{ marginRight: 4 }} />Cycle complete</span>
          {complete.next_forecast_period && (
            <span>Next period: <strong>{complete.next_forecast_period}</strong></span>
          )}
          {complete.rows_ingested != null && (
            <span>Rows ingested: <strong>{complete.rows_ingested.toLocaleString()}</strong></span>
          )}
          {complete.cumulative_rows != null && (
            <span>Cumulative: <strong>{complete.cumulative_rows.toLocaleString()}</strong></span>
          )}
        </div>
      )}
    </div>
  )
}
