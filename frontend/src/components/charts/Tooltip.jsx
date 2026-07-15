export function ChartTooltip({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--s2)', border: '0.5px solid var(--bs)',
      borderRadius: 'var(--r)', padding: '8px 12px',
      fontSize: '11px', fontFamily: 'var(--font)',
      boxShadow: '0 6px 24px rgba(0,0,0,.5)'
    }}>
      {label && <div style={{ color: 'var(--tm)', marginBottom: '5px', fontWeight: 600 }}>{label}</div>}
      {payload.map((e, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: e.color, flexShrink: 0 }} />
          <span style={{ color: 'var(--ts)' }}>{e.name}:</span>
          <span style={{ color: 'var(--tp)', fontWeight: 500 }}>
            {fmt ? fmt(e.value, e.name) : e.value}
          </span>
        </div>
      ))}
    </div>
  )
}
