export default function Logo({ size = 'md', showTagline = false, className = '', style = {}, onClick }) {
  const sizes = {
    sm: { height: 28, markW: 88, markH: 22, fontSize: 14, subSize: 8 },
    md: { height: 36, markW: 110, markH: 28, fontSize: 17, subSize: 9 },
    lg: { height: 48, markW: 140, markH: 36, fontSize: 22, subSize: 10 },
  }
  const s = sizes[size] || sizes.md

  return (
    <div
      className={`amasci-logo ${className}`}
      onClick={onClick}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: onClick ? 'pointer' : 'default', userSelect: 'none', ...style }}
    >
      <svg width={s.markW} height={s.markH} viewBox="0 0 110 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="lg1" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0984e3" />
            <stop offset="100%" stopColor="#6c5ce7" />
          </linearGradient>
          <linearGradient id="lg2" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0984e3" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#6c5ce7" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        {/* Mark — hexagonal supply chain node */}
        <rect x="1" y="1" width="26" height="26" rx="6" fill="url(#lg2)" stroke="url(#lg1)" strokeWidth="1.2" />

        {/* Hexagon outline */}
        <path d="M14 5 L21 9 L21 17 L14 21 L7 17 L7 9 Z"
          stroke="url(#lg1)" strokeWidth="1.4" fill="none" strokeLinejoin="round" />

        {/* Cross links */}
        <line x1="14" y1="5" x2="14" y2="21" stroke="#0984e3" strokeWidth="0.8" strokeOpacity="0.35" />
        <line x1="7" y1="9" x2="21" y2="17" stroke="#6c5ce7" strokeWidth="0.8" strokeOpacity="0.35" />
        <line x1="7" y1="17" x2="21" y2="9" stroke="#6c5ce7" strokeWidth="0.8" strokeOpacity="0.35" />

        {/* Nodes */}
        <circle cx="14" cy="5"  r="1.8" fill="#0984e3" />
        <circle cx="21" cy="9"  r="1.8" fill="#6c5ce7" />
        <circle cx="21" cy="17" r="1.8" fill="#00b894" />
        <circle cx="14" cy="21" r="1.8" fill="#6c5ce7" />
        <circle cx="7"  cy="17" r="1.8" fill="#e17055" />
        <circle cx="7"  cy="9"  r="1.8" fill="#0984e3" />

        {/* Center nexus */}
        <circle cx="14" cy="13" r="3.2" fill="url(#lg1)" />
        <circle cx="14" cy="13" r="1.4" fill="#fff" />

        {/* Wordmark */}
        <text x="33" y="17.5" fontFamily="Inter, system-ui, sans-serif" fontSize="13" fontWeight="700"
          letterSpacing="0.5" fill="#1a1d23">AMASCI</text>

        {/* Phase badge */}
        <rect x="82" y="8" width="26" height="12" rx="3" fill="rgba(9,132,227,0.1)" stroke="rgba(9,132,227,0.25)" strokeWidth="0.8" />
        <text x="95" y="17.5" fontFamily="Inter, system-ui, sans-serif" fontSize="7.5" fontWeight="600"
          fill="#0984e3" textAnchor="middle" letterSpacing="0.2">Phase 1</text>
      </svg>

      {showTagline && (
        <div style={{ fontSize: s.subSize, color: 'var(--tm)', fontWeight: 500, letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>
          Adaptive Supply Chain Intelligence
        </div>
      )}
    </div>
  )
}
