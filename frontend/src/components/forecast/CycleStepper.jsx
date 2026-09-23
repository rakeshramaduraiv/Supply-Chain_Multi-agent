/**
 * CycleStepper.jsx — Backend-authoritative 7-stage forecast lifecycle
 *
 * Renders ONLY what the backend reports. No localStorage lifecycle state.
 * No cycleStep counter. No hardcoded durations or completion percentages.
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
import { useState } from 'react'
import { Play, Upload, Loader, RotateCcw, AlertTriangle } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const STAGE_ICONS = {
  0: '🔮', 1: '📥', 2: '🔗', 3: '📊', 4: '⚡', 5: '🔄', 6: '🔮',
}

function stageBadgeClass(status) {
  if (!status) return 'bdg-med'
  if (status === 'COMPLETED') return 'bdg-low'
  if (status === 'SKIPPED')   return 'bdg-blue'
  if (status === 'FAILED')    return 'bdg-high'
  if (status === 'RUNNING')   return 'bdg-blue'
  return 'bdg-med'
}

function stageLabel(status) {
  if (!status) return 'Pending'
  if (status === 'COMPLETED') return 'Completed'
  if (status === 'SKIPPED')   return 'Skipped'
  if (status === 'FAILED')    return 'Failed'
  if (status === 'RUNNING')   return 'Running…'
  return 'Pending'
}

function stageSummary(stage, stageStatus) {
  if (!stageStatus) return null
  const d = stageStatus.detail || {}
  const status = stageStatus.status

  if (status === 'SKIPPED') {
    const reason = d.reason || stageStatus.error || 'Skipped'
    return <span style={{ color: 'var(--tm)' }}>Skipped — {reason}</span>
  }
  if (status === 'FAILED') {
    return <span style={{ color: 'var(--red, #e17055)' }}>Failed — {stageStatus.error || 'unknown error'}</span>
  }
  if (status !== 'COMPLETED') return null

  switch (stage) {
    case 0: return (
      <span>
        {d.total_forecasts ?? '—'} entities forecast for <strong>{d.target_period || '—'}</strong>
        {d.trained_through ? ` · model trained through ${d.trained_through}` : ''}
      </span>
    )
    case 1: return (
      <span>
        {d.rows?.toLocaleString() ?? '—'} rows ingested
        {d.duplicates_dropped > 0 ? ` · ${d.duplicates_dropped} duplicates dropped` : ''}
        {d.continuity_warnings > 0 ? ` · ${d.continuity_warnings} continuity warning(s)` : ''}
      </span>
    )
    case 2: return (
      <span>
        {d.rows_matched?.toLocaleString() ?? '—'} matched · {d.rows_excluded?.toLocaleString() ?? '—'} unmatched
        {d.match_rate != null ? ` · match rate ${(d.match_rate * 100).toFixed(1)}%` : ''}
      </span>
    )
    case 3: return (
      <span>
        {d.demand_mape != null ? `MAPE ${d.demand_mape.toFixed(2)}%` : ''}
        {d.demand_mae  != null ? ` · MAE ${d.demand_mae.toFixed(3)}` : ''}
        {d.demand_rmse != null ? ` · RMSE ${d.demand_rmse.toFixed(3)}` : ''}
        {d.late_delivery_f1 != null ? ` · F1 ${d.late_delivery_f1.toFixed(3)}` : ''}
        {!d.demand_mape && !d.demand_mae ? 'Metrics computed' : ''}
      </span>
    )
    case 4: return (
      <span>
        {d.edges_evolved != null ? `${d.edges_evolved} edges evolved` : 'TPKE evolution complete'}
      </span>
    )
    case 5: return (
      <span>
        {d.cumulative_rows?.toLocaleString() ?? '—'} cumulative rows
        {d.retrained_models?.length > 0 ? ` · retrained: ${d.retrained_models.join(', ')}` : ' · no retrain'}
      </span>
    )
    case 6: return (
      <span>
        Next period forecast generated
        {d.target_period ? ` for ${d.target_period}` : ''}
      </span>
    )
    default: return null
  }
}

export default function CycleStepper({
  cycleState,          // full response from GET /cycle/state
  isCycleLoading,
  onIssueForecast,     // (period) => void
  onUploadActuals,     // (period) => void — scrolls to upload zone
  onReset,             // () => void
  isIssuingForecast,
  isUploadingActuals,
  currentPeriod,       // the period currently being worked on
}) {
  const [showResetConfirm, setShowResetConfirm] = useState(false)

  if (isCycleLoading) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--tm)' }}>
          <Loader size={16} className={styles.spin} style={{ marginRight: 8 }} />
          Loading lifecycle state…
        </div>
      </div>
    )
  }

  const availablePeriods = cycleState?.available_periods || []
  const nextExpected     = cycleState?.next_expected_period
  const trainedThrough   = cycleState?.trained_through || '—'

  // Find the period entry we're displaying
  const activePeriodEntry = availablePeriods.find(p => p.period === currentPeriod)
    || availablePeriods[0]

  if (!activePeriodEntry) {
    return (
      <div id="lifecycle-anchor" className={styles.timelineCard}>
        <div style={{ padding: 24, color: 'var(--tm)', fontSize: 12 }}>
          No holdout periods available. Check that actuals_real/ contains CSV files.
        </div>
      </div>
    )
  }

  const stageStatuses = activePeriodEntry.stage_statuses || {}
  const stageReached  = activePeriodEntry.stage_reached ?? -1
  const isComplete    = activePeriodEntry.is_complete
  const canUpload     = activePeriodEntry.can_upload
  const lockedReason  = activePeriodEntry.locked_reason

  // The 7 canonical stages
  const stages = [0, 1, 2, 3, 4, 5, 6]

  const stage0Done = stageStatuses['0']?.status === 'COMPLETED'
  const isLocked   = !!lockedReason

  return (
    <div id="lifecycle-anchor" className={styles.timelineCard}>
      {/* Header */}
      <div className={styles.timelineHead}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--tp)' }}>
            Continuous Decision-Support Forecasting Lifecycle
          </div>
          <div style={{ fontSize: '11px', color: 'var(--tm)' }}>
            Forecast Issued → Ingest → Match → Evaluate → TPKE → Retrain → Forecast Next
            {' · '}Model trained through <strong>{trainedThrough}</strong>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className={`badge ${isComplete ? 'bdg-low' : 'bdg-blue'}`}>
            {isComplete ? 'Complete' : `Stage ${Math.max(stageReached, 0)} of 6`}
          </span>
          {/* Reset button */}
          {!showResetConfirm ? (
            <button
              className="btn btn-sm"
              style={{ fontSize: 10, padding: '2px 8px', opacity: 0.7 }}
              onClick={() => setShowResetConfirm(true)}
              title="Reset lifecycle for demo"
            >
              <RotateCcw size={10} /> Reset
            </button>
          ) : (
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: 'var(--tm)' }}>Delete all cycle state?</span>
              <button className="btn btn-sm" style={{ fontSize: 10, padding: '2px 8px', background: 'var(--red, #e17055)', color: '#fff' }}
                onClick={() => { setShowResetConfirm(false); onReset?.() }}>
                Confirm
              </button>
              <button className="btn btn-sm" style={{ fontSize: 10, padding: '2px 8px' }}
                onClick={() => setShowResetConfirm(false)}>
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Period selector */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 12px', borderBottom: '1px solid var(--b)', flexWrap: 'wrap' }}>
        {availablePeriods.map(ap => (
          <span
            key={ap.period}
            className={`badge ${ap.period === activePeriodEntry.period ? 'bdg-blue' : ap.is_complete ? 'bdg-low' : ap.locked_reason ? 'bdg-med' : 'bdg-med'}`}
            style={{ cursor: 'default', fontSize: 10 }}
            title={ap.locked_reason || (ap.is_complete ? 'Complete' : 'In progress')}
          >
            {ap.period}
            {ap.is_complete ? ' ✓' : ap.locked_reason ? ' 🔒' : ''}
          </span>
        ))}
      </div>

      {/* Locked notice */}
      {isLocked && (
        <div style={{ padding: '8px 12px', background: 'var(--s0)', borderBottom: '1px solid var(--b)', display: 'flex', gap: 6, alignItems: 'center', fontSize: 11, color: 'var(--tm)' }}>
          <AlertTriangle size={12} />
          {lockedReason}
        </div>
      )}

      {/* Stage grid */}
      <div className={styles.timelineGrid}>
        {stages.map(stage => {
          const ss = stageStatuses[String(stage)]
          const status = ss?.status || null
          const durationMs = ss?.duration_ms

          // Progress bar: COMPLETED or SKIPPED = 100%, RUNNING = animated, else 0%
          const progWidth = (status === 'COMPLETED' || status === 'SKIPPED') ? '100%'
            : status === 'RUNNING' ? '60%' : '0%'

          // Is this stage actionable right now?
          const isStage0Action = stage === 0 && !stage0Done && !isLocked
          const isStage1Action = stage === 1 && stage0Done && !stageStatuses['1'] && canUpload

          return (
            <div
              key={stage}
              className={`${styles.stepItem} ${stage === stageReached + 1 && !isLocked ? styles.stepItemActive : ''}`}
            >
              <div className={styles.stepHeader}>
                <span style={{ color: 'var(--tm)' }}>
                  {STAGE_ICONS[stage]} STAGE {stage}
                </span>
                <span className={`badge ${stageBadgeClass(status)}`}>
                  {stageLabel(status)}
                </span>
              </div>

              <div className={styles.stepTitle}>
                {cycleState?.stage_names?.[stage] || `Stage ${stage}`}
              </div>

              <div className={styles.stepMeta}>
                <span>
                  {durationMs != null ? `${(durationMs / 1000).toFixed(2)}s` : '—'}
                </span>
                <span style={{ color: 'var(--tm)', fontSize: 9 }}>
                  {activePeriodEntry.period}
                </span>
              </div>

              <div className={styles.progressBar}>
                <div
                  className={styles.progressFill}
                  style={{
                    width: progWidth,
                    transition: 'width 0.4s ease',
                    background: status === 'SKIPPED' ? 'var(--blue)' : status === 'FAILED' ? 'var(--red, #e17055)' : undefined,
                  }}
                />
              </div>

              <div className={styles.stepSummary}>
                {stageSummary(stage, ss) || (
                  <span style={{ color: 'var(--tm)' }}>
                    {isLocked ? lockedReason : 'Pending'}
                  </span>
                )}
              </div>

              {/* Stage 0 action: Issue Forecast */}
              {isStage0Action && (
                <div className={styles.stepAction}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ width: '100%' }}
                    disabled={isIssuingForecast}
                    onClick={() => onIssueForecast?.(activePeriodEntry.period)}
                  >
                    {isIssuingForecast
                      ? <><Loader size={11} className={styles.spin} /> Generating…</>
                      : <><Play size={11} /> Generate Forecast for {activePeriodEntry.period}</>}
                  </button>
                </div>
              )}

              {/* Stage 1 action: Upload Actuals */}
              {isStage1Action && (
                <div className={styles.stepAction}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ width: '100%' }}
                    disabled={isUploadingActuals}
                    onClick={() => onUploadActuals?.(activePeriodEntry.period)}
                  >
                    {isUploadingActuals
                      ? <><Loader size={11} className={styles.spin} /> Uploading…</>
                      : <><Upload size={11} /> Upload Actuals for {activePeriodEntry.period}</>}
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
