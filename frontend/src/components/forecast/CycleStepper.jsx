/**
 * CycleStepper.jsx — Backend-authoritative forecast lifecycle stepper.
 *
 * Rules enforced here:
 *  - Period selector driven exclusively from GET /dataset/available-periods
 *  - Stage list driven exclusively from cycleState.available_periods[].stage_statuses
 *  - No hardcoded stage count, no hardcoded period list
 *  - SKIPPED renders as "Skipped" and does NOT leave stepper running
 *  - FAILED halts the stepper and shows the error
 *  - RUNNING stages time out after RUNNING_TIMEOUT_MS with a retry action
 *  - Terminal state shown after all 4 periods complete — no 5th period offered
 *  - Upload button names the exact period expected: "Upload actuals for Nov 2017"
 *  - Page reload reconstructs from backend (no localStorage lifecycle state)
 */
import { useState, useRef, useEffect } from 'react'
import { Play, Upload, Loader, RotateCcw, AlertTriangle, CheckCircle, Clock, RefreshCw } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const RUNNING_TIMEOUT_MS = 120_000  // 2 minutes — if no terminal status arrives, show error

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
    return <span style={{ color: 'var(--red,#e17055)', fontSize: 10 }}>Failed — {ss.error || 'unknown error'}</span>
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

// Stages that are allowed to be SKIPPED (correct behaviour, not an error)
const SKIPPABLE_STAGES = new Set([2, 3, 4])

export default function CycleStepper({
  cycleState,
  isCycleLoading,
  onIssueForecast,
  onUploadActuals,
  onReset,
  onRefetch,
  isIssuingForecast,
  isUploadingActuals,
}) {
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const fileInputRef = useRef(null)

  // Track when each RUNNING stage started so we can time out
  const runningStartRef = useRef({})  // { [stageKey]: timestamp }
  const [timedOutStages, setTimedOutStages] = useState({})  // { [stageKey]: true }

  // Detect RUNNING stages and start timeout clock
  useEffect(() => {
    if (!cycleState) return
    const now = Date.now()
    const newTimedOut = { ...timedOutStages }
    let changed = false

    for (const ap of (cycleState.available_periods || [])) {
      for (const [stageKey, ss] of Object.entries(ap.stage_statuses || {})) {
        const key = `${ap.period}:${stageKey}`
        if (ss.status === 'RUNNING') {
          if (!runningStartRef.current[key]) {
            runningStartRef.current[key] = now
          } else if (now - runningStartRef.current[key] > RUNNING_TIMEOUT_MS && !newTimedOut[key]) {
            newTimedOut[key] = true
            changed = true
          }
        } else {
          // Stage reached terminal — clear timeout tracking
          delete runningStartRef.current[key]
          if (newTimedOut[key]) {
            delete newTimedOut[key]
            changed = true
          }
        }
      }
    }
    if (changed) setTimedOutStages(newTimedOut)
  })

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

  const availablePeriods  = cycleState?.available_periods || []
  const nextExpected      = cycleState?.next_expected_period
  const trainedThrough    = cycleState?.trained_through || '—'
  const stageNames        = cycleState?.stage_names || {}
  const allComplete       = cycleState?.all_complete === true
  const totalAvailable    = cycleState?.total_available ?? availablePeriods.length
  const totalComplete     = cycleState?.total_complete ?? 0
  // Distinct period tracking (Defect 3)
  const standingForecastPeriod = cycleState?.standing_forecast_period
  const awaitingActualsFor     = cycleState?.awaiting_actuals_for

  // Active period = next_expected, or last period if all complete
  const activePeriodEntry = availablePeriods.find(p => p.period === nextExpected)
    || (allComplete ? availablePeriods[availablePeriods.length - 1] : null)
    || availablePeriods[0]

  if (!activePeriodEntry && !allComplete) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: 24, color: 'var(--tm)', fontSize: 12 }}>
          No holdout periods available. Ensure actuals_real/ contains CSV files and initialization has run.
        </div>
      </div>
    )
  }

  // ── Terminal state: all periods complete ──────────────────────────────────
  if (allComplete) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <CheckCircle size={20} style={{ color: '#00b894', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--tp)' }}>
                All available periods processed — {totalComplete} of {totalAvailable} complete
              </div>
              <div style={{ fontSize: 11, color: 'var(--tm)', marginTop: 2 }}>
                DataCo holdout window exhausted. No further actuals files exist beyond 2018-01.
                Model trained through <strong>{trainedThrough}</strong>.
              </div>
            </div>
          </div>

          {/* Period summary */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {availablePeriods.map(ap => (
              <span key={ap.period} className="badge bdg-low" style={{ fontSize: 10 }}>
                {ap.period} ✓
              </span>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            {!showResetConfirm ? (
              <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }}
                onClick={() => setShowResetConfirm(true)}>
                <RotateCcw size={11} /> Reset for Demo
              </button>
            ) : (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--tm)' }}>Delete all cycle state?</span>
                <button className="btn btn-sm"
                  style={{ fontSize: 11, padding: '3px 10px', background: 'var(--red,#e17055)', color: '#fff' }}
                  onClick={() => { setShowResetConfirm(false); onReset?.() }}>Confirm</button>
                <button className="btn btn-sm" style={{ fontSize: 11, padding: '3px 10px' }}
                  onClick={() => setShowResetConfirm(false)}>Cancel</button>
              </div>
            )}
          </div>
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

  // Check if any stage is FAILED — halt the stepper
  const failedStage = Object.entries(stageStatuses).find(([, ss]) => ss.status === 'FAILED')
  const haltedByFailure = !!failedStage

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) onUploadActuals?.(activePeriodEntry.period, file)
    e.target.value = ''
  }

  // Build period label for upload button (Defect 3c)
  const periodLabel = (() => {
    const p = awaitingActualsFor || activePeriodEntry.period
    const MONTH_NAMES = {
      '01': 'January', '02': 'February', '03': 'March', '04': 'April',
      '05': 'May', '06': 'June', '07': 'July', '08': 'August',
      '09': 'September', '10': 'October', '11': 'November', '12': 'December',
    }
    const parts = p.split('-')
    return parts.length === 2 ? `${MONTH_NAMES[parts[1]] || parts[1]} ${parts[0]}` : p
  })()

  // Stages to render: keys present in stageStatuses UNION [0..6] for pending display
  // Always show all 7 stages (0-6) — pending ones show as Pending
  const stageKeys = [0, 1, 2, 3, 4, 5, 6]

  return (
    <div id="lifecycle-anchor" className={styles.timelineCard}>
      {/* Hidden file input */}
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
          {/* Defect 3b: show three periods explicitly */}
          <div style={{ fontSize: 11, color: 'var(--tm)', marginTop: 2 }}>
            {awaitingActualsFor && standingForecastPeriod && awaitingActualsFor !== standingForecastPeriod ? (
              <>
                Actuals uploaded: <strong>{awaitingActualsFor}</strong>
                {' · '}Standing forecast: <strong>{standingForecastPeriod}</strong>
                {' · '}Model trained through: <strong>{trainedThrough}</strong>
              </>
            ) : (
              <>
                Current period: <strong>{activePeriodEntry.period}</strong>
                {' · '}Model trained through: <strong>{trainedThrough}</strong>
              </>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className={`badge ${isComplete ? 'bdg-low' : haltedByFailure ? 'bdg-high' : isCycleLoading ? 'bdg-blue' : 'bdg-med'}`}>
            {isComplete ? '✓ Complete' : haltedByFailure ? '✗ Failed' : stageReached >= 0 ? `Stage ${stageReached} / 6` : 'Not started'}
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

      {/* Period tabs — only available periods, never fabricated ones */}
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

      {/* FAILED halt banner */}
      {haltedByFailure && (
        <div style={{ padding: '8px 12px', background: 'rgba(225,112,85,0.08)', borderBottom: '1px solid var(--red,#e17055)', display: 'flex', gap: 8, alignItems: 'center', fontSize: 11 }}>
          <AlertTriangle size={13} style={{ color: 'var(--red,#e17055)', flexShrink: 0 }} />
          <span style={{ color: 'var(--red,#e17055)', fontWeight: 700 }}>
            Stage {failedStage[0]} failed — {failedStage[1].error || 'see stage detail below'}
          </span>
          <button className="btn btn-sm" style={{ marginLeft: 'auto', fontSize: 10 }}
            onClick={() => onRefetch?.()}>
            <RefreshCw size={10} /> Retry
          </button>
        </div>
      )}

      {/* Stage grid — rendered from backend stage_statuses, never hardcoded */}
      <div className={styles.timelineGrid}>
        {stageKeys.map(stage => {
          const ss         = stageStatuses[String(stage)]
          const status     = ss?.status || null
          const durationMs = ss?.duration_ms
          const isRunning  = status === 'RUNNING'
          const isFailed   = status === 'FAILED'
          const isSkipped  = status === 'SKIPPED'
          const isCompleted= status === 'COMPLETED'
          const timedOutKey = `${activePeriodEntry.period}:${stage}`
          const isTimedOut = timedOutStages[timedOutKey]

          // A stage is "active" if it's the next one to run and not locked/halted
          const isActive = !isLocked && !haltedByFailure && !isComplete
            && stage === stageReached + 1

          // Progress bar width
          const progWidth = (isCompleted || isSkipped) ? '100%'
            : (isRunning && !isTimedOut) ? '60%' : '0%'

          // Stage 0 button: show if stage 0 not done and not locked
          const showStage0Btn = stage === 0 && !stage0Done && !isLocked && !haltedByFailure

          // Stage 1 button: show if stage 0 done, stage 1 pending/failed, can upload
          // Defect 3c: button names the exact period
          const showStage1Btn = stage === 1 && stage0Done && stage1Pending && canUpload && !isLocked && !haltedByFailure

          return (
            <div key={stage}
              className={`${styles.stepItem} ${isActive || isRunning ? styles.stepItemActive : ''}`}
              style={{ opacity: isLocked && stage > 0 ? 0.6 : 1 }}>

              <div className={styles.stepHeader}>
                <span style={{ color: 'var(--tm)', fontSize: 10 }}>
                  {STAGE_ICONS[stage]} STAGE {stage}
                </span>
                <span className={`badge ${badgeClass(isTimedOut ? 'FAILED' : status)}`} style={{ fontSize: 9 }}>
                  {isTimedOut ? 'Timed out' : stageLabel(status)}
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
                  animation: (isRunning && !isTimedOut) ? 'pulse 1.2s ease-in-out infinite' : 'none',
                  background: isSkipped ? 'var(--blue)'
                    : (isFailed || isTimedOut) ? 'var(--red,#e17055)' : undefined,
                }} />
              </div>

              <div className={styles.stepSummary}>
                {isTimedOut ? (
                  <span style={{ color: 'var(--red,#e17055)', fontSize: 10 }}>
                    No response from backend after {RUNNING_TIMEOUT_MS / 1000}s
                  </span>
                ) : (
                  <StageSummary stage={stage} ss={ss} />
                )}
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

              {/* Stage 1: Upload Actuals — names the exact period (Defect 3c) */}
              {showStage1Btn && (
                <div className={styles.stepAction}>
                  <button className="btn btn-primary btn-sm" style={{ width: '100%', fontSize: 11 }}
                    disabled={isUploadingActuals}
                    onClick={() => fileInputRef.current?.click()}>
                    {isUploadingActuals
                      ? <><Loader size={11} className={styles.spin} /> Uploading…</>
                      : <><Upload size={11} /> Upload actuals for {periodLabel}</>}
                  </button>
                  <div style={{ fontSize: 9, color: 'var(--tm)', marginTop: 3, textAlign: 'center' }}>
                    Select {activePeriodEntry.period.replace('-', '_')}_actual.csv
                  </div>
                </div>
              )}

              {/* Stages 2-6 running indicator */}
              {isRunning && !isTimedOut && stage > 1 && (
                <div className={styles.stepAction}>
                  <div style={{ fontSize: 10, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Loader size={10} className={styles.spin} /> Processing…
                  </div>
                </div>
              )}

              {/* Timeout retry */}
              {isTimedOut && (
                <div className={styles.stepAction}>
                  <button className="btn btn-sm" style={{ fontSize: 10, width: '100%' }}
                    onClick={() => {
                      const k = `${activePeriodEntry.period}:${stage}`
                      delete runningStartRef.current[k]
                      setTimedOutStages(prev => { const n = { ...prev }; delete n[k]; return n })
                      onRefetch?.()
                    }}>
                    <RefreshCw size={10} /> Retry
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Completion banner for current period */}
      {isComplete && !allComplete && (
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
