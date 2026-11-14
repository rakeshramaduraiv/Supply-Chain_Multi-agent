/**
 * StageRow.jsx
 * One stage row — all five statuses: COMPLETED, SKIPPED, RUNNING, FAILED, PENDING.
 * SKIPPED renders as "Skipped — {reason}", never as COMPLETED.
 * FAILED shows error text.
 * RUNNING shows pulsing indicator; times out after TIMEOUT_MS.
 */
import { Loader, RefreshCw } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const TIMEOUT_MS = 120_000

const STAGE_ICONS = { 0: '🔮', 1: '📥', 2: '🔗', 3: '📊', 4: '⚡', 5: '🔄', 6: '🔮' }

function pill(status, timedOut) {
  if (timedOut)              return { label: 'Timed out', cls: 'bdg-high' }
  if (!status)               return { label: 'Pending',   cls: 'bdg-med'  }
  if (status === 'COMPLETED') return { label: 'Completed', cls: 'bdg-low'  }
  if (status === 'SKIPPED')   return { label: 'Skipped',   cls: 'bdg-blue' }
  if (status === 'RUNNING')   return { label: 'Running…',  cls: 'bdg-blue' }
  if (status === 'FAILED')    return { label: 'Failed',    cls: 'bdg-high' }
  return { label: status, cls: 'bdg-med' }
}

function detail(stage, ss) {
  if (!ss) return null
  const d = ss.detail ?? {}
  const status = ss.status

  if (status === 'SKIPPED') return `Skipped \u2014 ${d.reason ?? ss.error ?? '\u2014'}`
  if (status === 'FAILED')  return `Error: ${ss.error ?? 'unknown'}`
  if (status === 'RUNNING') return 'Processing\u2026'
  if (status !== 'COMPLETED') return null

  const parts = []
  switch (stage) {
    case 0:
      if (d.total_forecasts != null) parts.push(`${d.total_forecasts} entities`)
      if (d.target_period)           parts.push(`for ${d.target_period}`)
      if (d.trained_through)         parts.push(`trained through ${d.trained_through}`)
      break
    case 1:
      if (d.rows != null)            parts.push(`${d.rows.toLocaleString()} rows`)
      if (d.duplicates_dropped > 0)  parts.push(`${d.duplicates_dropped} dupes dropped`)
      if (d.continuity_warnings > 0) parts.push(`${d.continuity_warnings} warnings`)
      break
    case 2:
      if (d.rows_matched != null)    parts.push(`${d.rows_matched.toLocaleString()} matched`)
      if (d.rows_excluded != null)   parts.push(`${d.rows_excluded.toLocaleString()} unmatched`)
      if (d.match_rate != null)      parts.push(`${(d.match_rate * 100).toFixed(1)}% match rate`)
      break
    case 3:
      if (d.demand_mape != null)      parts.push(`MAPE ${d.demand_mape.toFixed(2)}%`)
      if (d.demand_mae != null)       parts.push(`MAE ${d.demand_mae.toFixed(3)}`)
      if (d.late_delivery_f1 != null) parts.push(`F1 ${d.late_delivery_f1.toFixed(3)}`)
      if (!parts.length)              parts.push('Metrics computed')
      break
    case 4:
      parts.push(d.edges_evolved != null ? `${d.edges_evolved} edges evolved` : 'TPKE complete')
      break
    case 5:
      if (d.cumulative_rows != null)   parts.push(`${d.cumulative_rows.toLocaleString()} cumulative rows`)
      if (d.retrained_models?.length)  parts.push(`retrained: ${d.retrained_models.join(', ')}`)
      break
    case 6:
      parts.push(d.target_period ? `Next forecast: ${d.target_period}` : 'Next forecast generated')
      break
    default: break
  }
  return parts.join(' · ') || 'Complete'
}

export default function StageRow({
  stage, stageName, ss,
  runningStartedAt,   // timestamp when RUNNING began (from parent)
  onRetry,
}) {
  const status   = ss?.status ?? null
  const durationMs = ss?.duration_ms ?? null

  const timedOut = status === 'RUNNING'
    && runningStartedAt != null
    && Date.now() - runningStartedAt > TIMEOUT_MS

  const { label, cls } = pill(status, timedOut)
  const detailText = timedOut
    ? `No response from backend after ${TIMEOUT_MS / 1000}s`
    : detail(stage, ss)

  const progWidth =
    (status === 'COMPLETED' || status === 'SKIPPED') ? '100%' :
    (status === 'RUNNING' && !timedOut) ? '60%' : '0%'

  const progColor =
    status === 'SKIPPED'          ? '#60a5fa' :
    (status === 'FAILED' || timedOut) ? '#e17055' :
    undefined

  return (
    <div className={`${styles.stepItem} ${(status === 'RUNNING' || status === null) ? '' : ''}`}>
      <div className={styles.stepHeader}>
        <span style={{ fontSize: 9.5, color: 'var(--tm)', fontWeight: 700 }}>
          {STAGE_ICONS[stage] ?? '○'} STAGE {stage}
        </span>
        <span className={`badge ${cls}`} style={{ fontSize: 9 }}>{label}</span>
      </div>

      <div className={styles.stepTitle}>{stageName}</div>

      <div className={styles.stepMeta}>
        <span>{durationMs != null ? `${(durationMs / 1000).toFixed(2)}s` : '\u2014'}</span>
      </div>

      <div className={styles.progressBar}>
        <div
          className={styles.progressFill}
          style={{
            width: progWidth,
            background: progColor,
            transition: status === 'RUNNING' ? 'none' : 'width 0.5s ease',
            animation: (status === 'RUNNING' && !timedOut) ? 'pulse 1.2s ease-in-out infinite' : 'none',
          }}
        />
      </div>

      <div className={styles.stepSummary} style={{
        color: status === 'FAILED' || timedOut ? '#e17055' :
               status === 'SKIPPED' ? 'var(--tm)' : undefined,
      }}>
        {detailText ?? <span style={{ color: 'var(--tm)' }}>Pending</span>}
      </div>

      {status === 'RUNNING' && !timedOut && (
        <div className={styles.stepAction} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--blue)' }}>
          <Loader size={10} className={styles.spin} /> Processing…
        </div>
      )}

      {(timedOut || status === 'FAILED') && onRetry && (
        <div className={styles.stepAction}>
          <button className="btn btn-sm" style={{ fontSize: 10, width: '100%' }} onClick={onRetry}>
            <RefreshCw size={10} /> Retry
          </button>
        </div>
      )}
    </div>
  )
}
