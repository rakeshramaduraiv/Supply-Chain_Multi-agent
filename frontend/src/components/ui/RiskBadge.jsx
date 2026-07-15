export default function RiskBadge({ level, label }) {
  const l = (level || 'low').toLowerCase()
  const cls = l === 'critical' ? 'bdg-high' : l === 'high' ? 'bdg-high' : l === 'medium' ? 'bdg-med' : 'bdg-low'
  return (
    <span className={`badge ${cls}`}>
      <span className="bdg-dot" />
      {label || level || 'Low'}
    </span>
  )
}
