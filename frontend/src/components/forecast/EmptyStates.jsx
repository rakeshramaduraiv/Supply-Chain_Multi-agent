/**
 * EmptyStates.jsx
 * Every explicit state from C5 — never a blank panel or indefinite spinner.
 */
import { AlertTriangle, WifiOff, RefreshCw, CheckCircle, RotateCcw } from 'lucide-react'

export function BackendUnreachable({ onRetry }) {
  return (
    <div style={{
      background: 'rgba(225,112,85,0.08)', border: '1.5px solid #e17055',
      borderRadius: 12, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <WifiOff size={16} style={{ color: '#e17055' }} />
        <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--tp)' }}>Cannot reach backend</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--tm)' }}>
        The backend at <code>localhost:8001</code> is not responding. Ensure the server is running.
      </div>
      {onRetry && (
        <button className="btn btn-sm" style={{ alignSelf: 'flex-start', fontSize: 11 }} onClick={onRetry}>
          <RefreshCw size={11} /> Retry
        </button>
      )}
    </div>
  )
}

export function NoPeriodsAvailable({ actualsDir }) {
  return (
    <div style={{
      background: 'rgba(245,158,11,0.08)', border: '1.5px solid #f59e0b',
      borderRadius: 12, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <AlertTriangle size={16} style={{ color: '#f59e0b' }} />
        <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--tp)' }}>No actuals files found</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--tm)' }}>
        No holdout periods are available in <code>{actualsDir ?? 'backend/data/actuals_real/'}</code>.
        Ensure the four actuals CSVs and the holdout manifest are present.
      </div>
      <div style={{ fontSize: 11, color: '#f59e0b', fontWeight: 700 }}>
        Run: <code>make bootstrap</code>
      </div>
    </div>
  )
}

export function ModelsNotInitialized() {
  return (
    <div style={{
      background: 'rgba(245,158,11,0.08)', border: '1.5px solid #f59e0b',
      borderRadius: 12, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <AlertTriangle size={16} style={{ color: '#f59e0b' }} />
        <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--tp)' }}>Models not initialized</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--tm)' }}>
        Stage 0 returned <code>NOT_INITIALIZED</code>. The ML models have not been trained yet.
      </div>
      <div style={{ fontSize: 11, color: '#f59e0b', fontWeight: 700 }}>
        Run: <code>make bootstrap</code> or <code>POST /api/v1/initialization/run</code>
      </div>
    </div>
  )
}

export function AllPeriodsComplete({ cycleState, onReset, showResetConfirm, setShowResetConfirm }) {
  const total    = cycleState?.total_available ?? 4
  const complete = cycleState?.total_complete  ?? total
  const trained  = cycleState?.trained_through ?? '\u2014'
  const periods  = cycleState?.available_periods ?? []

  return (
    <div style={{
      background: 'rgba(0,184,148,0.08)', border: '1.5px solid #00b894',
      borderRadius: 12, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <CheckCircle size={20} style={{ color: '#00b894', flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--tp)' }}>
            All {complete} of {total} periods processed
          </div>
          <div style={{ fontSize: 11, color: 'var(--tm)', marginTop: 2 }}>
            DataCo holdout window exhausted. Model trained through <strong>{trained}</strong>.
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {periods.map(ap => (
          <span key={ap.period} className="badge bdg-low" style={{ fontSize: 10 }}>
            {ap.period} ✓
          </span>
        ))}
      </div>

      {!showResetConfirm ? (
        <button className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start', fontSize: 11 }}
          onClick={() => setShowResetConfirm(true)}>
          <RotateCcw size={11} /> Reset for Demo
        </button>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--tm)' }}>Delete all cycle state?</span>
          <button className="btn btn-sm"
            style={{ fontSize: 11, padding: '3px 10px', background: '#e17055', color: '#fff' }}
            onClick={() => { setShowResetConfirm(false); onReset?.() }}>Confirm</button>
          <button className="btn btn-sm" style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => setShowResetConfirm(false)}>Cancel</button>
        </div>
      )}
    </div>
  )
}

export function LiveUpdatesOffline() {
  return (
    <span style={{
      fontSize: 9, color: '#f59e0b', fontWeight: 600,
      display: 'inline-flex', alignItems: 'center', gap: 3,
    }}>
      <WifiOff size={9} /> live updates offline
    </span>
  )
}
