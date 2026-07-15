export default function ScoreBar({ score = 0, showValue = true }) {
  const pct = Math.min(Math.max(score * 100, 0), 100)
  const cls = score < 0.35 ? 'fill-low' : score < 0.65 ? 'fill-med' : 'fill-high'
  return (
    <div className="mini-bar">
      <div className="track">
        <div className={`fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      {showValue && <span className="val">{pct.toFixed(0)}%</span>}
    </div>
  )
}
