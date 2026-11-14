/**
 * CycleHeader.jsx
 * Three-period bar: awaiting actuals · standing forecast · model trained through
 * Plus period progress counter.
 * Every value comes from cycleState — null renders an em dash, never a guess.
 */
import styles from '../../pages/ForecastPage.module.css'

export default function CycleHeader({ cycleState }) {
  if (!cycleState) return null

  const awaiting  = cycleState.awaiting_actuals_for      ?? null
  const standing  = cycleState.standing_forecast_period  ?? null
  const trained   = cycleState.trained_through           ?? null
  const total     = cycleState.total_available           ?? null
  const complete  = cycleState.total_complete            ?? null

  const dash = '\u2014'

  return (
    <div className={styles.cycleHeaderBar}>
      <div className={styles.cycleHeaderPeriods}>
        <span>
          <span className={styles.cycleHeaderLabel}>Awaiting actuals:</span>
          <span className={styles.cycleHeaderVal}>{awaiting ?? dash}</span>
        </span>
        <span className={styles.cycleHeaderSep}>·</span>
        <span>
          <span className={styles.cycleHeaderLabel}>Standing forecast:</span>
          <span className={styles.cycleHeaderVal}>{standing ?? dash}</span>
        </span>
        <span className={styles.cycleHeaderSep}>·</span>
        <span>
          <span className={styles.cycleHeaderLabel}>Model trained through:</span>
          <span className={styles.cycleHeaderVal}>{trained ?? dash}</span>
        </span>
      </div>
      {total != null && complete != null && (
        <div className={styles.cycleHeaderProgress}>
          Period <strong>{complete + 1 <= total ? complete + 1 : complete}</strong> of <strong>{total}</strong>
        </div>
      )}
    </div>
  )
}
