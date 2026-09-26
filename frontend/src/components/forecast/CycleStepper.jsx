/**
 * CycleStepper.jsx — Backend-authoritative 7-stage forecast lifecycle
 *
 * Stage map (matches cycle_state_store.py):
 *   0  Forecast Issued      — forecast for P generated before actuals exist
 *   1  Ingest & Validate    — actuals uploaded, schema + continuity checked
 *   2  Match                — actuals joined to standing forecast
 *   3  Evaluate             — metrics computed on matched pairs
 *   4  TPKE Evolve          — edges created / strengthened / decayed / pruned
 *   5  Store & Retrain      — period appended, models retrained
 *   6  Forecast Next        — forecast for P+1 generated
 */
import { useState, useRef } from 'react'
import { Play, Upload, Loader, RotateCcw, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const STAGE_ICONS = { 0: '🔮', 1: '📥', 2: '🔗', 3: '📊', 4: '⚡', 5: '🔄', 6: '🔮' }

const STAGE_NAMES_FALLBACK = {
  0: 'Forecast Issued',
  1: 'Ingest & Validate',
  2: 'Match',
  3: 'Evaluate',
  4: 'TPKE Evolve',
  5: 'Store & Retrain',
  6: 'Forecast Next',
}

function badgeClass(status) {
  if (status === 'COMPLETED') return 'bdg-low'
  if (status === 'SKIPPED')   return 'bdg-blue'
  if (status === 'FAILED')    return 'bdg-high'
  if (status === 'RUNNING')   return 'bdg-blue'
  return 'bdg-med'
}

function stageLabel(status) {
  if (status === 'COMPLETED') return 'Completed'
  if (status === 'SKIPPED')   return 'Skipped'
  if (status === 'FAILED')    return 'Failed'
  if (status === 'RUNNING')   return 'Running…'
  return 'Pending'
}

function StageSummary({ stage, ss }) {
  if (!ss) return <span style={{ color: 'var(--tm)', fontSize: 10 }}>Pending</span>
  const d = ss.detail || {}
  const status = ss.status

  if (status === 'SKIPPED')
    return <span style={{ color: 'var(--tm)', fontSize: 10 }}>Skipped — {d.reason || ss.error || '—'}</span>
  if (status === 'FAILED')
    return <span style={{ color: 'var(--red,#e17055)', fontSize: 10 }}>Failed — {ss.error || 'unknown'}</span>
  if (status === 'RUNNING')
    return <span style={{ color: 'var(--blue)', fontSize: 10 }}>Running…</span>
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
      if (d.demand_mape != null)     parts.push(`MAPE ${d.demand_mape.toFixed(2)}%`)
      if (d.demand_mae != null)      parts.push(`MAE ${d.demand_mae.toFixed(3)}`)
      if (d.late_delivery_f1 != null)parts.push(`F1 ${d.late_delivery_f1.toFixed(3)}`)
      if (!parts.length)             parts.push('Metrics computed')
      break
    case 4:
      parts.push(d.edges_evolved != null ? `${d.edges_evolved} edges evolved` : 'TPKE complete')
      break
    case 5:
      if (d.cumulative_rows != null) parts.push(`${d.cumulative_rows.toLocaleString()} cumulative rows`)
      if (d.retrained_models?.length) parts.push(`retrained: ${d.retrained_models.join(', ')}`)
      break
    case 6:
      parts.push(d.target_period ? `Next forecast: ${d.target_period}` : 'Next forecast generated')
      break
    default: break
  }
  return <span style={{ fontSize: 10 }}>{parts.join(' · ') || 'Complete'}</span>
}

export default function CycleStepper({
  cycleState,
  isCycleLoading,
  onIssueForecast,
  onUploadActuals,
  onReset,
  isIssuingForecast,
  isUploadingActuals,
  currentPeriod,
}) {
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const fileInputRef = useRef(null)

  if (isCycleLoading && !cycleState) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--tm)' }}>
          <Loader size={16} className={styles.spin} style={{ marginRight: 8 }} />
          Loading lifecycle…
        </div>
      </div>
    )
  }

  const availablePeriods = cycleState?.available_periods || []
  const nextExpected     = cycleState?.next_expected_period
  const trainedThrough   = cycleState?.trained_through || '—'
  // stage_names keys come as strings from JSON
  const stageNames       = cycleState?.stage_names || {}

  const activePeriodEntry = availablePeriods.find(p => p.period === currentPeriod)
    || availablePeriods.find(p => p.period === nextExpected)
    || availablePeriods[0]

  if (!activePeriodEntry) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: 24, color: 'var(--tm)', fontSize: 12 }}>
          No holdout periods available. Ensure actuals_real/ contains CSV files and initialization has run.
        </div>
      </div>
    )
  }

  const stageStatuses = activePeriodEntry.stage_statuses || {}
  const stageReached  = activePeriodEntry.stage_reached ?? -1
  const isComplete    = activePeriodEntry.is_complete
  const canUpload     = activePeriodEntry.can_upload
  const lockedReason  = activePeriodEntry.locked_reason
  const isLocked      = !!lockedReason

  const stage0Done    = stageStatuses['0']?.status === 'COMPLETED'
  const stage1Status  = stageStatuses['1']?.status
  const stage1Pending = !stage1Status || stage1Status === 'FAILED'

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) onUploadActuals?.(activePeriodEntry.period, file)
    e.target.value = ''
  }

  return (
    <div id="lifecycle-anchor" className={styles.timelineCard}>
      {/* Hidden file input for actuals upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Header */}
      <div className={styles.timelineHead}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--tp)' }}>
            Continuous Decision-Support Forecasting Lifecycle
          </div>
          <div style={{ fontSize: 11, color: 'var(--tm)' }}>
            Forecast → Ingest → Match → Evaluate → TPKE → Retrain → Forecast Next
            {' · '}Model trained through <strong>{trainedThrough}</strong>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className={`badge ${isComplete ? 'bdg-low' : isCycleLoading ? 'bdg-blue' : 'bdg-med'}`}>
            {isComplete ? '✓ Complete' : stageReached >= 0 ? `Stage ${stageReached} / 6` : 'Not started'}
          </span>
          {!showResetConfirm ? (
            <button className="btn btn-sm" style={{ fontSize: 10, padding: '2px 8px', opacity: 0.6 }}
              onClick={() => setShowResetConfirm(true)} title="Reset lifecycle">
              <RotateCcw size={10} /> Reset
            </button>
          ) : (
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: 'var(--tm)' }}>Delete all cycle state?</span>
              <button className="btn btn-sm"
                style={{ fontSize: 10, padding: '2px 8px', background: 'var(--red,#e17055)', color: '#fff' }}
                onClick={() => { setShowResetConfirm(false); onReset?.() }}>Confirm</button>
              <button className="btn btn-sm" style={{ fontSize: 10, padding: '2px 8px' }}
                onClick={() => setShowResetConfirm(false)}>Cancel</button>
            </div>
          )}
        </div>
      </div>

      {/* Period tabs */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 12px', borderBottom: '1px solid var(--b)', flexWrap: 'wrap' }}>
        {availablePeriods.map(ap => (
          <span key={ap.period}
            className={`badge ${ap.period === activePeriodEntry.period ? 'bdg-blue' : ap.is_complete ? 'bdg-low' : 'bdg-med'}`}
            style={{ fontSize: 10, cursor: 'default' }}
            title={ap.locked_reason || (ap.is_complete ? 'Complete' : ap.period === nextExpected ? 'Current' : 'Locked')}>
            {ap.period}{ap.is_complete ? ' ✓' : ap.locked_reason ? ' 🔒' : ap.period === nextExpected ? ' ←' : ''}
          </span>
        ))}
      </div>

      {/* Locked notice */}
      {isLocked && (
        <div style={{ padding: '8px 12px', background: 'var(--s0)', borderBottom: '1px solid var(--b)', display: 'flex', gap: 6, alignItems: 'center', fontSize: 11, color: 'var(--tm)' }}>
          <AlertTriangle size={12} /> {lockedReason}
        </div>
      )}

      {/* Stage grid */}
      <div className={styles.timelineGrid}>
        {[0, 1, 2, 3, 4, 5, 6].map(stage => {
          const ss        = stageStatuses[String(stage)]
          const status    = ss?.status || null
          const durationMs = ss?.duration_ms
          const isActive  = stage === stageReached + 1 && !isLocked && !isComplete
          const isRunning = status === 'RUNNING'

          const progWidth = (status === 'COMPLETED' || status === 'SKIPPED') ? '100%'
            : isRunning ? '60%' : '0%'

          const showStage0Btn = stage === 0 && !stage0Done && !isLocked
          const showStage1Btn = stage === 1 && stage0Done && stage1Pending && canUpload && !isLocked

          return (
            <div key={stage}
              className={`${styles.stepItem} ${isActive || isRunning ? styles.stepItemActive : ''}`}
              style={{ opacity: isLocked && stage > 0 ? 0.6 : 1 }}>

              <div className={styles.stepHeader}>
                <span style={{ color: 'var(--tm)', fontSize: 10 }}>
                  {STAGE_ICONS[stage]} STAGE {stage}
                </span>
                <span className={`badge ${badgeClass(status)}`} style={{ fontSize: 9 }}>
                  {stageLabel(status)}
                </span>
              </div>

              <div className={styles.stepTitle} style={{ fontSize: 11, fontWeight: 700 }}>
                {stageNames[String(stage)] || STAGE_NAMES_FALLBACK[stage]}
              </div>

              <div className={styles.stepMeta}>
                <span style={{ fontSize: 9, color: 'var(--tm)' }}>
                  {durationMs != null ? `${(durationMs / 1000).toFixed(2)}s` : '—'}
                </span>
                <span style={{ fontSize: 9, color: 'var(--tm)' }}>
                  {activePeriodEntry.period}
                </span>
              </div>

              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{
                  width: progWidth,
                  transition: isRunning ? 'none' : 'width 0.5s ease',
                  animation: isRunning ? 'pulse 1.2s ease-in-out infinite' : 'none',
                  background: status === 'SKIPPED' ? 'var(--blue)'
                    : status === 'FAILED' ? 'var(--red,#e17055)' : undefined,
                }} />
              </div>

              <div className={styles.stepSummary}>
                <StageSummary stage={stage} ss={ss} />
                {!ss && isLocked && (
                  <span style={{ color: 'var(--tm)', fontSize: 10 }}>{lockedReason}</span>
                )}
              </div>

              {/* Stage 0: Generate Forecast */}
              {showStage0Btn && (
                <div className={styles.stepAction}>
                  <button className="btn btn-primary btn-sm" style={{ width: '100%', fontSize: 11 }}
                    disabled={isIssuingForecast}
                    onClick={() => onIssueForecast?.(activePeriodEntry.period)}>
                    {isIssuingForecast
                      ? <><Loader size={11} className={styles.spin} /> Generating…</>
                      : <><Play size={11} /> Generate Forecast for {activePeriodEntry.period}</>}
                  </button>
                </div>
              )}

              {/* Stage 1: Upload Actuals */}
              {showStage1Btn && (
                <div className={styles.stepAction}>
                  <button className="btn btn-primary btn-sm" style={{ width: '100%', fontSize: 11 }}
                    disabled={isUploadingActuals}
                    onClick={() => fileInputRef.current?.click()}>
                    {isUploadingActuals
                      ? <><Loader size={11} className={styles.spin} /> Uploading…</>
                      : <><Upload size={11} /> Upload Actuals for {activePeriodEntry.period}</>}
                  </button>
                  <div style={{ fontSize: 9, color: 'var(--tm)', marginTop: 3, textAlign: 'center' }}>
                    Select {activePeriodEntry.period.replace('-', '_')}_actual.csv from actuals_real/
                  </div>
                </div>
              )}

              {/* Stages 2-6 running indicator */}
              {isRunning && stage > 1 && (
                <div className={styles.stepAction}>
                  <div style={{ fontSize: 10, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Loader size={10} className={styles.spin} /> Processing…
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Completion banner */}
      {isComplete && (
        <div style={{ padding: '10px 14px', background: 'rgba(0,184,148,0.08)', borderTop: '1px solid var(--b)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
          <CheckCircle size={13} style={{ color: '#00b894' }} />
          <span style={{ color: '#00b894', fontWeight: 700 }}>
            Cycle complete for {activePeriodEntry.period}
          </span>
          {nextExpected && (
            <span style={{ color: 'var(--tm)', marginLeft: 'auto' }}>
              Next: {nextExpected} →
            </span>
          )}
        </div>
      )}
    </div>
  )
}
