/**
 * StageStepper.jsx
 * Renders the 7 stage rows for the active/inspected period.
 * Stage count comes from cycleState.stage_names — never hardcoded.
 * Exactly two user actions: Generate Forecast (Stage 0) and Upload Actuals (Stage 1).
 * All other stages are automatic.
 */
import { useRef, useState, useEffect, useMemo } from 'react'
import { Play, Upload, Loader, AlertTriangle, CheckCircle } from 'lucide-react'
import StageRow from './StageRow'
import styles from '../../pages/ForecastPage.module.css'

const MONTH_NAMES = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April',
  '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
}

function fullPeriodLabel(period) {
  const parts = period?.split('-')
  return parts?.length === 2 ? `${MONTH_NAMES[parts[1]] ?? parts[1]} ${parts[0]}` : (period ?? '')
}

export default function StageStepper({
  periodEntry,          // one entry from available_periods
  cycleState,
  isIssuingForecast,
  isUploadingActuals,
  onIssueForecast,
  onUploadActuals,
  onRefetch,
}) {
  const fileInputRef = useRef(null)
  // Track when each stage entered RUNNING state for timeout detection
  const [runningStartTimes, setRunningStartTimes] = useState({})

  const stageNames = cycleState?.stage_names ?? {}
  const stageKeys  = Object.keys(stageNames).length > 0
    ? Object.keys(stageNames).map(Number).sort((a, b) => a - b)
    : [0, 1, 2, 3, 4, 5, 6]

  const stageStatuses = periodEntry?.stage_statuses ?? {}
  const period        = periodEntry?.period ?? ''
  const canUpload     = periodEntry?.can_upload ?? false
  const lockedReason  = periodEntry?.locked_reason ?? null
  const isComplete    = periodEntry?.is_complete ?? false
  const nextExpected  = cycleState?.next_expected_period
  const isActivePeriod = period === nextExpected

  const stage0Status = stageStatuses['0']?.status
  const stage0Done   = stage0Status === 'COMPLETED'
  const stage1Status = stageStatuses['1']?.status
  const stage1Done   = stage1Status === 'COMPLETED'

  // Track RUNNING stage start times — only re-run when stage_statuses changes
  const stageStatusesKey = useMemo(
    () => stageKeys.map(s => `${s}:${stageStatuses[String(s)]?.status ?? ''}`).join(','),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stageKeys.join(','), JSON.stringify(stageStatuses)]
  )

  useEffect(() => {
    const now = Date.now()
    setRunningStartTimes(prev => {
      const next = { ...prev }
      let changed = false
      stageKeys.forEach(s => {
        const key = String(s)
        const status = stageStatuses[key]?.status
        if (status === 'RUNNING' && !next[key]) {
          next[key] = now; changed = true
        } else if (status !== 'RUNNING' && next[key]) {
          delete next[key]; changed = true
        }
      })
      return changed ? next : prev
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stageStatusesKey])

  const failedEntry = Object.entries(stageStatuses).find(([, ss]) => ss.status === 'FAILED')

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) onUploadActuals?.(period, file)
    e.target.value = ''
  }

  const periodLabel = fullPeriodLabel(cycleState?.awaiting_actuals_for ?? period)

  // Show Stage 0 button: only for active period, stage 0 not done, not locked
  const showForecastBtn = isActivePeriod && !stage0Done && !lockedReason
  // Show upload button: only for active period, stage 0 done, stage 1 not done, can_upload
  const showUploadBtn   = isActivePeriod && stage0Done && !stage1Done && canUpload
  // Show locked reason in place of upload: stage 0 done, stage 1 not done, can_upload false
  const showLockedUpload = isActivePeriod && stage0Done && !stage1Done && !canUpload

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* FAILED halt banner */}
      {failedEntry && (
        <div style={{
          padding: '8px 12px', marginBottom: 8,
          background: 'rgba(225,112,85,0.08)', border: '1px solid #e17055',
          borderRadius: 8, display: 'flex', gap: 8, alignItems: 'center', fontSize: 11,
        }}>
          <AlertTriangle size={13} style={{ color: '#e17055', flexShrink: 0 }} />
          <span style={{ color: '#e17055', fontWeight: 700 }}>
            Stage {failedEntry[0]} failed — {failedEntry[1].error ?? 'see detail below'}
          </span>
          <button className="btn btn-sm" style={{ marginLeft: 'auto', fontSize: 10 }}
            onClick={() => onRefetch?.()}>
            Retry
          </button>
        </div>
      )}

      {/* Locked notice for non-active periods */}
      {lockedReason && !isActivePeriod && (
        <div style={{
          padding: '6px 10px', marginBottom: 8,
          background: 'var(--s0)', border: '1px solid var(--b)',
          borderRadius: 8, display: 'flex', gap: 6, alignItems: 'center',
          fontSize: 11, color: 'var(--tm)',
        }}>
          <AlertTriangle size={11} /> {lockedReason}
        </div>
      )}

      {/* Stage grid */}
      <div className={styles.timelineGrid}>
        {stageKeys.map(stage => (
          <StageRow
            key={stage}
            stage={stage}
            stageName={stageNames[String(stage)] ?? `Stage ${stage}`}
            ss={stageStatuses[String(stage)] ?? null}
            runningStartedAt={runningStartTimes[String(stage)] ?? null}
            onRetry={onRefetch}
          />
        ))}
      </div>

      {/* User actions — only two, only for active period */}
      {isActivePeriod && (
        <div style={{ display: 'flex', gap: 10, padding: '10px 0 4px', flexWrap: 'wrap' }}>
          {showForecastBtn && (
            <button
              className="btn btn-primary btn-sm"
              style={{ fontSize: 11 }}
              disabled={isIssuingForecast}
              onClick={() => onIssueForecast?.(period)}
            >
              {isIssuingForecast
                ? <><Loader size={11} className={styles.spin} /> Generating…</>
                : <><Play size={11} /> Generate forecast for {period}</>}
            </button>
          )}

          {showUploadBtn && (
            <button
              className="btn btn-primary btn-sm"
              style={{ fontSize: 11 }}
              disabled={isUploadingActuals}
              onClick={() => fileInputRef.current?.click()}
            >
              {isUploadingActuals
                ? <><Loader size={11} className={styles.spin} /> Uploading…</>
                : <><Upload size={11} /> Upload actuals for {periodLabel}</>}
            </button>
          )}

          {showLockedUpload && (
            <div style={{ fontSize: 11, color: 'var(--tm)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <AlertTriangle size={11} style={{ color: '#f59e0b' }} />
              {lockedReason ?? 'Upload not available for this period'}
            </div>
          )}

          {!showForecastBtn && stage0Done && !showUploadBtn && !showLockedUpload && !isComplete && (
            <div style={{ fontSize: 11, color: 'var(--tm)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Loader size={11} className={styles.spin} style={{ color: 'var(--blue)' }} />
              Stages 2–6 running automatically…
            </div>
          )}
        </div>
      )}

      {/* Completion banner */}
      {isComplete && (
        <div style={{
          padding: '8px 12px', marginTop: 8,
          background: 'rgba(0,184,148,0.08)', border: '1px solid #00b894',
          borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8, fontSize: 11,
        }}>
          <CheckCircle size={13} style={{ color: '#00b894' }} />
          <span style={{ color: '#00b894', fontWeight: 700 }}>Cycle complete for {period}</span>
          {cycleState?.next_expected_period && (
            <span style={{ color: 'var(--tm)', marginLeft: 'auto' }}>
              Next: {cycleState.next_expected_period} →
            </span>
          )}
        </div>
      )}
    </div>
  )
}
