export default function RiskGauge({ score = 0, size = 110, label, color }) {
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.37
  const sw = size * 0.075
  const circumference = 2 * Math.PI * r
  const sweep = 0.75 * circumference
  const offset = sweep - (score * sweep)

  function polarToXY(angleDeg) {
    const rad = (angleDeg - 90) * (Math.PI / 180)
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
  }

  function arcPath(start, end) {
    const s = polarToXY(start)
    const e = polarToXY(end)
    const large = (end - start) > 180 ? 1 : 0
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
  }

  const riskColor = color || (
    score < 0.35 ? 'var(--rl)' :
    score < 0.65 ? 'var(--rm)' : 'var(--rh)'
  )

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="gauge-wrap">
      <path d={arcPath(135, 405)} fill="none"
        stroke="var(--s3)" strokeWidth={sw} strokeLinecap="round" />
      <path d={arcPath(135, 405)} fill="none"
        stroke={riskColor} strokeWidth={sw} strokeLinecap="round"
        strokeDasharray={`${sweep} ${circumference}`}
        strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)' }} />
      <text x={cx} y={cy - 4} textAnchor="middle" dominantBaseline="central"
        style={{ fill: 'var(--tp)', fontSize: size * 0.17, fontWeight: 500, fontFamily: 'var(--font)' }}>
        {Math.round(score * 100)}%
      </text>
      {label && (
        <text x={cx} y={cy + size * 0.14} textAnchor="middle"
          style={{ fill: 'var(--tm)', fontSize: size * 0.09, fontFamily: 'var(--font)' }}>
          {label}
        </text>
      )}
    </svg>
  )
}
