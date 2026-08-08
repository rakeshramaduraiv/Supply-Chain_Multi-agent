/**
 * components/domain/CycleStageTracker.jsx
 *
 * Renders the six backend cycle stages live.
 * Receives `stages` from useCycleStream — a map keyed by stage number.
 * Each row shows: status pill, duration, detail summary, error string on FAILED.
 *
 * Status colours:
 *   RUNNING   → blue pulse
 *   COMPLETED → green
 *   SKIPPED   → neutral grey  (a visible skip is a feature, not an error)
 *   FAILED    → red + error string
 *   PENDING   → muted (not yet started)
 *
 * Metrics (from stage 3 detail) render source="measured" in full contrast,
 * source="unavailable" as an em-dash — never a plausible-looking placeholder.
 */

import { Activity, CheckCircle, SkipForward, XCircle, Loader, Clock } from 'lucide-react'

const STAGE_DEFS = [
  { stage: 1, name: 'Ingest & Validate' },
  { stage: 2, name: 'Match Forecast vs Actual' },
  { stage: 3, name: 'Compute Metrics' },
  { stage: 4, name: 'TPKE Evolution' },
  { stage: 5, name: 'Store & Retrain' },
  { stage: 6, name: 'Forecast Next Period' },
]

// ── Status pill ───────────────────────────────────────────────────────────────

function StatusPill({ status }) {
  if (!status || status === 'PENDING') {
    return (
      <span style={pill('#64748b', 'rgba(100,116,139,0.12)')}>
        <Clock size={10} /> Pending
      </span>
    )
  }
  if (status === 'RUNNING') {
    return (
      <span style={{ ...pill('#3b82f6', 'rgba(59,130,246,0.12)'), animation: 'pulse 1.2s infinite' }}>
        <Loader size={10} style={{ animation: 'spin 1s linear infinite' }} /> Running
      </span>
    )
  }
  if (status === 'COMPLETED') {
    return (
      <span style={pill('#00b894', 'rgba(0,184,148,0.12)')}>
        <CheckCircle size={10} /> Completed
      </span>
    )
  }
  if (status === 'SKIPPED') {
    return (
      <span style={pill('#94a3b8', 'rgba(148,163,184,0.12)')}>
        <SkipForward size={10} /> Skipped
      </span>
    )
  }
  if (status === 'FAILED') {
    return (
      <span style={pill('#ef4444', 'rgba(239,68,68,0.12)')}>
        <XCircle size={10} /> Failed
      </span>
    )
  }
  return null
}

function pill(color, bg) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 10, fontWeight: 700, color,
    background: bg, border: `1px solid ${color}33`,
    borderRadius: 6, padding: '2px 7px', whiteSpace: 'nowrap',
  }
}

// ── Row border colour by status ───────────────────────────────────────────────

function rowStyle(status) {
  const base = {
    display: 'flex', alignItems: 'flex-start', gap: 12,
    padding: '10px 14px', borderRadius: 8,
    border: '1px solid var(--b)',
    background: 'var(--s0)',
    transition: 'border-color 0.2s',
  }
  if (status === 'RUNNING')   return { ...base, border: '1px solid #3b82f6', background: 'rgba(59,130,246,0.04)' }
  if (status === 'COMPLETED') return { ...base, border: '1px solid rgba(0,184,148,0.35)', background: 'rgba(0,184,148,0.03)' }
  if (status === 'FAILED')    return { ...base, border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.03)' }
  if (status === 'SKIPPED')   return { ...base, border: '1px solid rgba(148,163,184,0.3)', opacity: 0.75 }
  return base
}

// ── Metric value with source tag ──────────────────────────────────────────────

function MetricValue({ entry }) {
  // entry is { value, source } from CycleResponse.metrics
  if (!entry || entry.source === 'unavailable') {
    return <span style={{ color: 'var(--tm)' }}>—</span>
  }
  const v = typeof entry.value === 'number' ? entry.value.toFixed(4) : entry.value
  return <span style={{ color: 'var(--tp)', fontWeight: 700 }}>{v}</span>
}

// ── Detail summary for each stage ─────────────────────────────────────────────

function DetailSummary({ stage, event, metrics }) {
  if (!event || event.status === 'PENDING') return null

  const d = event.detail || {}

  if (event.status === 'SKIPPED') {
    return (
      <span style={{ fontSize: 10, color: '#94a3b8' }}>
        {d.reason || 'Skipped'}
      </span>
    )
  }

  if (stage === 1) {
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)' }}>
        {d.rows != null ? `${d.rows.toLocaleString()} rows` : ''}
        {d.duplicates_dropped > 0 ? ` · ${d.duplicates_dropped} duplicates dropped` : ''}
        {d.period ? ` · period ${d.period}` : ''}
      </span>
    )
  }
  if (stage === 2) {
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)' }}>
        {d.rows_matched != null ? `${d.rows_matched.toLocaleString()} matched` : ''}
        {d.rows_excluded != null ? ` · ${d.rows_excluded.toLocaleString()} excluded` : ''}
        {d.forecast_anchors != null ? ` · ${d.forecast_anchors} anchors` : ''}
      </span>
    )
  }
  if (stage === 3 && metrics) {
    // Render measured metrics from CycleResponse.metrics (source-tagged)
    const keys = Object.keys(metrics)
    if (keys.length === 0) return <span style={{ fontSize: 10, color: 'var(--ts)' }}>No metrics computed</span>
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {keys.map(k => (
          <span key={k}>
            <span style={{ color: 'var(--tm)' }}>{k.replace(/_/g, ' ')}: </span>
            <MetricValue entry={metrics[k]} />
          </span>
        ))}
      </span>
    )
  }
  if (stage === 4) {
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)' }}>
        {d.edges_evolved != null ? `${d.edges_evolved} edges evolved` : ''}
      </span>
    )
  }
  if (stage === 5) {
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)' }}>
        {d.cumulative_rows != null ? `${d.cumulative_rows.toLocaleString()} cumulative rows` : ''}
        {d.retrained_models?.length ? ` · retrained: ${d.retrained_models.join(', ')}` : ''}
      </span>
    )
  }
  if (stage === 6) {
    return (
      <span style={{ fontSize: 10, color: 'var(--ts)' }}>
        {d.next_period ? `Next period: ${d.next_period}` : ''}
      </span>
    )
  }
  return null
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CycleStageTracker({ stages = {}, complete = null, metrics = null, period }) {
  // Derive overall status label
  const stageList = STAGE_DEFS.map(def => stages[def.stage])
  const anyRunning   = stageList.some(s => s?.status === 'RUNNING')
  const anyFailed    = stageList.some(s => s?.status === 'FAILED')
  const anySkipped   = stageList.some(s => s?.status === 'SKIPPED')
  const allDone      = stageList.every(s => s && s.status !== 'RUNNING' && s.status !== 'PENDING')

  let overallLabel = 'Waiting'
  let overallColor = 'var(--tm)'
  if (anyRunning)                    { overallLabel = 'Running…';  overallColor = '#3b82f6' }
  else if (complete && anyFailed)    { overallLabel = 'Failed';    overallColor = '#ef4444' }
  else if (complete && anySkipped)   { overallLabel = 'Partial';   overallColor = '#f59e0b' }
  else if (complete)                 { overallLabel = 'Completed'; overallColor = '#00b894' }

  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--b)',
      borderRadius: 12, padding: 18,
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--tp)', display: 'flex', alignItems: 'center', gap: 7 }}>
          <Activity size={15} style={{ color: 'var(--blue)' }} />
          Six-Stage Upload Cycle Pipeline
          {period && <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tm)' }}>· {period}</span>}
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: overallColor }}>
          {overallLabel}
        </span>
      </div>

      {/* Stage rows */}
      {STAGE_DEFS.map(({ stage, name }) => {
        const event  = stages[stage]
        const status = event?.status || 'PENDING'
        const durationMs = event?.duration_ms

        return (
          <div key={stage} style={rowStyle(status)}>
            {/* Stage number */}
            <div style={{
              minWidth: 24, height: 24, borderRadius: '50%',
              background: status === 'COMPLETED' ? '#00b894'
                        : status === 'RUNNING'   ? '#3b82f6'
                        : status === 'FAILED'    ? '#ef4444'
                        : status === 'SKIPPED'   ? '#94a3b8'
                        : 'var(--b)',
              color: status === 'PENDING' ? 'var(--tm)' : '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 800, flexShrink: 0, marginTop: 1,
            }}>
              {stage}
            </div>

            {/* Content */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)' }}>{name}</span>
                <StatusPill status={status} />
                {durationMs != null && status !== 'RUNNING' && (
                  <span style={{ fontSize: 10, color: 'var(--tm)' }}>
                    {durationMs < 1000
                      ? `${Math.round(durationMs)}ms`
                      : `${(durationMs / 1000).toFixed(1)}s`}
                  </span>
                )}
              </div>

              <DetailSummary
                stage={stage}
                event={event}
                metrics={stage === 3 ? metrics : null}
              />

              {/* Error string — only on FAILED */}
              {status === 'FAILED' && event?.error && (
                <div style={{
                  fontSize: 10, color: '#ef4444',
                  background: 'rgba(239,68,68,0.07)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: 5, padding: '3px 7px', marginTop: 2,
                  fontFamily: 'var(--mono, monospace)',
                }}>
                  {event.error}
                </div>
              )}
            </div>
          </div>
        )
      })}

      {/* cycle.complete summary row */}
      {complete && (
        <div style={{
          marginTop: 4, padding: '8px 14px',
          background: anyFailed ? 'rgba(239,68,68,0.05)' : 'rgba(0,184,148,0.05)',
          border: `1px solid ${anyFailed ? 'rgba(239,68,68,0.25)' : 'rgba(0,184,148,0.25)'}`,
          borderRadius: 8, fontSize: 11, color: 'var(--ts)',
          display: 'flex', gap: 16, flexWrap: 'wrap',
        }}>
          {complete.summary?.rows_ingested != null && (
            <span><span style={{ color: 'var(--tm)' }}>Ingested: </span>
              <strong>{complete.summary.rows_ingested.toLocaleString()}</strong>
            </span>
          )}
          {complete.summary?.rows_matched != null && (
            <span><span style={{ color: 'var(--tm)' }}>Matched: </span>
              <strong>{complete.summary.rows_matched.toLocaleString()}</strong>
            </span>
          )}
          {complete.summary?.cumulative_rows != null && (
            <span><span style={{ color: 'var(--tm)' }}>Cumulative: </span>
              <strong>{complete.summary.cumulative_rows.toLocaleString()}</strong>
            </span>
          )}
          <span style={{ marginLeft: 'auto', fontWeight: 700, color: overallColor }}>
            {complete.summary?.status || overallLabel}
          </span>
        </div>
      )}
    </div>
  )
}
