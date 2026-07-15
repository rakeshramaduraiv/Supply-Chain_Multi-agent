import { useEffect, useRef, useState } from 'react'

export default function KpiCard({ label, value, unit, foot, delta, deltaDir, color }) {
  const [display, setDisplay] = useState(0)
  const rafRef = useRef(null)
  const numVal = typeof value === 'number' ? value : parseFloat(value) || 0

  useEffect(() => {
    const start = performance.now()
    const duration = 800
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(numVal * eased)
      if (progress < 1) rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
  }, [numVal])

  const formatted = numVal >= 1000
    ? Math.round(display).toLocaleString()
    : display.toFixed(numVal % 1 === 0 ? 0 : 1)

  return (
    <div className="kpi" style={color ? { borderLeftColor: color } : undefined}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-val">
        {formatted}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {(foot || delta) && (
        <div className="kpi-foot">
          {delta && <span className={deltaDir === 'up' ? 'kpi-up' : 'kpi-dn'}>{delta}</span>}
          {foot && <span>{foot}</span>}
        </div>
      )}
    </div>
  )
}
