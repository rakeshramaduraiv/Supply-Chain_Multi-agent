import sys, re

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\RiskPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

print('FILE SIZE:', len(raw), file=sys.stderr)

# ── PATCH 1: add expandedSlide state ──────────────────────────────────────
# Find the filterYear useState line and the next blank line + comment
marker1 = b"const [filterYear, setFilterYear] = useState('All')"
idx1 = raw.find(marker1)
print('marker1 at:', idx1, file=sys.stderr)

if idx1 >= 0:
    # find end of that line (after \r\n)
    end1 = raw.find(b'\r\n', idx1) + 2
    insert1 = b"  const [expandedSlide, setExpandedSlide] = useState(null)\r\n"
    # only insert if not already there
    if b'expandedSlide' not in raw:
        raw = raw[:end1] + insert1 + raw[end1:]
        print('PATCH1 applied', file=sys.stderr)
    else:
        print('PATCH1 already applied', file=sys.stderr)
else:
    print('PATCH1 marker not found', file=sys.stderr)

# ── PATCH 2: replace queueScroll content with accordion slides ────────────
old_queue_start = b'          <div className={s.queueScroll}>'
old_queue_end   = b'          </div>\r\n        </aside>'

i_start = raw.find(old_queue_start)
i_end   = raw.find(old_queue_end, i_start)
print('queue start:', i_start, 'end:', i_end, file=sys.stderr)

if i_start >= 0 and i_end >= 0:
    new_queue = b'''          <div className={s.queueScroll}>
            {filteredIncidents.map(i => {
              const isActive = selectedIssueId === i.id
              const isOpen = expandedSlide === i.id
              let sevColor = '#10b981'
              if (i.severity === 'Critical') sevColor = '#ef4444'
              if (i.severity === 'High') sevColor = '#f97316'
              if (i.severity === 'Medium') sevColor = '#eab308'
              return (
                <div key={i.id} className={`${s.incidentSlide} ${isActive ? s.incidentSlideActive : ''}`}>
                  <div className={s.slideHeader} onClick={() => setExpandedSlide(prev => prev === i.id ? null : i.id)}>
                    <span className={s.slideSeverityDot} style={{ background: sevColor }} />
                    <div className={s.slideHeaderText}>
                      <div className={s.slideIncidentName}>{i.name}</div>
                      <div className={s.slideIncidentMeta}>{i.type} \xc2\xb7 {i.region} \xc2\xb7 {i.periodLabel || i.period}</div>
                    </div>
                    <span className={s.slideRiskBadge} style={{ color: sevColor }}>{i.risk}</span>
                    <ChevronDown size={12} className={`${s.slideChevron} ${isOpen ? s.slideChevronOpen : ''}`} />
                  </div>
                  <div className={`${s.slideBody} ${isOpen ? s.slideBodyOpen : ''}`}>
                    <div className={s.slideBodyInner}>
                      <div className={s.slideKpiRow}>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Loss</span>
                          <span className={s.slideKpiVal} style={{ color: '#ef4444' }}>${i.financialLoss.toLocaleString()}</span>
                        </div>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Orders</span>
                          <span className={s.slideKpiVal}>{i.affectedOrders.toLocaleString()}</span>
                        </div>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Conf</span>
                          <span className={s.slideKpiVal} style={{ color: '#3b82f6' }}>{i.confidence}</span>
                        </div>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Delay</span>
                          <span className={s.slideKpiVal}>{i.expectedDelay}d</span>
                        </div>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Customers</span>
                          <span className={s.slideKpiVal}>{i.customers.toLocaleString()}</span>
                        </div>
                        <div className={s.slideKpiBox}>
                          <span className={s.slideKpiLabel}>Drop</span>
                          <span className={s.slideKpiVal} style={{ color: '#f97316' }}>-{i.forecastDrop}%</span>
                        </div>
                      </div>
                      <div className={s.slideTagRow}>
                        <span className={`${s.tag} ${i.status === 'Resolved' ? s.tagGreen : s.tagAmber}`}>{i.status}</span>
                        <span className={s.tag} style={{ background: `${sevColor}15`, color: sevColor, border: `1px solid ${sevColor}30` }}>{i.severity}</span>
                        {i._fromForecast && (
                          <span style={{ fontSize: '8px', background: '#dbeafe', color: '#1d4ed8', padding: '2px 6px', borderRadius: 8, fontWeight: 800, border: '1px solid #93c5fd' }}>\xf0\x9f\x93\x88 Forecast</span>
                        )}
                      </div>
                      <button
                        className={`${s.slideSelectBtn} ${isActive ? s.slideSelectBtnActive : ''}`}
                        onClick={() => handleIncidentSelect(i.id, i.type)}
                      >
                        {isActive ? '\xe2\x9c\x93 Currently Investigating' : 'Open Investigation \xe2\x86\x92'}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
'''
    raw = raw[:i_start] + new_queue + raw[i_end:]
    print('PATCH2 applied', file=sys.stderr)
else:
    print('PATCH2 markers not found', file=sys.stderr)

with open(path, 'wb') as f:
    f.write(raw)
print('DONE written', len(raw), file=sys.stderr)
