/**
 * PeriodRail.jsx
 * One card per entry in available_periods, in order.
 * Each card: label, row count, 7-dot stage strip, state badge.
 * Locked cards show locked_reason as visible text, not a tooltip.
 * Clicking a non-active card only inspects it — never acts out of order.
 */
import { Lock, CheckCircle, ChevronRight } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const MONTH_NAMES = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
  '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
  '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
}

function periodLabel(period) {
  const parts = period.split('-')
  return parts.length === 2 ? `${MONTH_NAMES[parts[1]] ?? parts[1]} ${parts[0]}` : period
}

function StageDot({ status }) {
  const color =
    status === 'COMPLETED' ? '#00b894' :
    status === 'SKIPPED'   ? '#60a5fa' :
    status === 'FAILED'    ? '#e17055' :
    status === 'RUNNING'   ? '#f59e0b' :
    'var(--b)'
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: color, flexShrink: 0,
    }} />
  )
}

export default function PeriodRail({ cycleState, inspectedPeriod, onInspect }) {
  if (!cycleState) return null

  const available   = cycleState.available_periods ?? []
  const nextExpected = cycleState.next_expected_period
  const stageNames  = cycleState.stage_names ?? {}
  const stageKeys   = Object.keys(stageNames).map(Number).sort((a, b) => a - b)

  return (
    <div className={styles.periodRail}>
      {available.map(ap => {
        const isActive   = ap.period === nextExpected
        const isComplete = ap.is_complete
        const isInspected = ap.period === inspectedPeriod
        const isLocked   = !!ap.locked_reason && !isActive && !isComplete

        return (
          <button
            key={ap.period}
            className={`${styles.periodCard} ${isActive ? styles.periodCardActive : ''} ${isInspected ? styles.periodCardInspected : ''} ${isComplete ? styles.periodCardComplete : ''}`}
            onClick={() => onInspect?.(ap.period)}
            title={isActive ? 'Current period' : isComplete ? 'Complete' : ap.locked_reason ?? ''}
          >
            <div className={styles.periodCardTop}>
              <span className={styles.periodCardLabel}>{periodLabel(ap.period)}</span>
              {isComplete && <CheckCircle size={12} style={{ color: '#00b894', flexShrink: 0 }} />}
              {isLocked   && <Lock size={11} style={{ color: 'var(--tm)', flexShrink: 0 }} />}
              {isActive   && <ChevronRight size={12} style={{ color: '#60a5fa', flexShrink: 0 }} />}
            </div>

            {ap.rows != null && (
              <div className={styles.periodCardRows}>{ap.rows.toLocaleString()} rows</div>
            )}

            {/* 7-dot stage strip */}
            <div className={styles.periodStageDots}>
              {stageKeys.map(s => (
                <StageDot key={s} status={ap.stage_statuses?.[String(s)]?.status ?? null} />
              ))}
            </div>

            {/* State label */}
            <div className={styles.periodCardState}>
              {isComplete ? (
                <span style={{ color: '#00b894', fontSize: 9, fontWeight: 700 }}>Complete</span>
              ) : isActive ? (
                <span style={{ color: '#60a5fa', fontSize: 9, fontWeight: 700 }}>Active</span>
              ) : isLocked ? (
                <span style={{ color: 'var(--tm)', fontSize: 9 }}>{ap.locked_reason}</span>
              ) : (
                <span style={{ color: 'var(--tm)', fontSize: 9 }}>Pending</span>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
