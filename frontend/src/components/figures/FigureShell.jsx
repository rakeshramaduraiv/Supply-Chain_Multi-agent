// src/components/figures/FigureShell.jsx
// Fixed 1200×700 white card, 32px padding, 1px #E0E0E0 border.
// Root id = `figure-{figureNumber}` for screenshot targeting.
import { useEffect, useState } from 'react'
import { FONT, CANVAS, PALETTE } from './figureTheme'

export default function FigureShell({
  figureNumber, title, subtitle, caption, children,
  loading, error, emptyMessage,
}) {
  const [ts, setTs] = useState(null)
  const hasContent = !loading && !error && !emptyMessage

  useEffect(() => { if (hasContent) setTs(new Date()) }, [hasContent])

  return (
    <div
      id={`figure-${figureNumber}`}
      style={{
        width: CANVAS.width, background: CANVAS.background,
        border: '1px solid #E0E0E0', borderRadius: 4,
        fontFamily: 'system-ui,-apple-system,sans-serif',
        boxSizing: 'border-box', overflow: 'hidden',
      }}
    >
      <style>{`@keyframes _fig_spin{to{transform:rotate(360deg)}}`}</style>

      {/* Centered header */}
      <div style={{ textAlign: 'center', padding: `${CANVAS.padding}px ${CANVAS.padding}px 0` }}>
        <div style={{ fontSize: FONT.title, fontWeight: 600, color: PALETTE.dark, lineHeight: 1.3 }}>
          Fig.&nbsp;{figureNumber}.&nbsp;&nbsp;{title}
        </div>
        {subtitle && (
          <div style={{ fontSize: FONT.footnote, color: PALETTE.grey, marginTop: 4 }}>
            {subtitle}
          </div>
        )}
        {/* Status badge top-right */}
        <div style={{ position: 'absolute', top: 12, right: 16, fontSize: 10, color: '#94a3b8' }}>
          {ts && hasContent && ts.toLocaleTimeString()}
        </div>
      </div>

      {/* Chart area */}
      <div style={{ padding: `16px ${CANVAS.padding}px` }}>
        {loading && (
          <div style={{ height: 500, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
            <div style={{ width: 36, height: 36, border: '3px solid #e2e8f0', borderTopColor: PALETTE.primary, borderRadius: '50%', animation: '_fig_spin .8s linear infinite' }} />
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Loading…</div>
          </div>
        )}
        {!loading && error && (
          <div style={{ height: 500, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <div style={{ fontSize: 30 }}>⚠️</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#ef4444' }}>Request failed</div>
            <div style={{ fontSize: 12, color: '#94a3b8', maxWidth: 400, textAlign: 'center' }}>
              {typeof error === 'string' ? error : 'Check API connection'}
            </div>
          </div>
        )}
        {!loading && !error && emptyMessage && (
          <div style={{ height: 500, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, border: '2px dashed #ccc', borderRadius: 6, margin: '0 8px' }}>
            <div style={{ fontSize: 30 }}>📭</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: PALETTE.grey }}>No data</div>
            <div style={{ fontSize: 12, color: '#888', maxWidth: 440, textAlign: 'center', fontFamily: 'monospace' }}>
              {emptyMessage}
            </div>
          </div>
        )}
        {hasContent && children}
      </div>

      {/* Caption centered below chart */}
      {caption && hasContent && (
        <div style={{ textAlign: 'center', padding: `0 ${CANVAS.padding}px ${CANVAS.padding}px`, fontSize: FONT.caption, color: '#444', lineHeight: 1.6 }}>
          {caption}
        </div>
      )}
    </div>
  )
}
