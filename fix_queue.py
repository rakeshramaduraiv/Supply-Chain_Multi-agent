import sys

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\RiskPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

# The patch script left mixed LF/CRLF. Find the queueScroll div start and the </aside> that closes leftSidebar.
# We'll replace everything from <div className={s.queueScroll}> up to and including </aside> (first one after it)

START = b'          <div className={s.queueScroll}>'
END   = b'        </aside>\r\n\r\n        {/* \xe7\xac\x8f\xe2\x95\x90\xe6\xa5\xb3 CENTER COLUMN'

i_start = raw.find(START)
i_end   = raw.find(END, i_start)

print('start:', i_start, 'end:', i_end, file=sys.stderr)

if i_start < 0 or i_end < 0:
    print('MARKERS NOT FOUND', file=sys.stderr)
    sys.exit(1)

NEW = (
    b'          <div className={s.queueScroll}>\r\n'
    b'            {filteredIncidents.map(i => {\r\n'
    b'              const isActive = selectedIssueId === i.id\r\n'
    b'              const isOpen = expandedSlide === i.id\r\n'
    b'              let sevColor = \'#10b981\'\r\n'
    b'              if (i.severity === \'Critical\') sevColor = \'#ef4444\'\r\n'
    b'              if (i.severity === \'High\') sevColor = \'#f97316\'\r\n'
    b'              if (i.severity === \'Medium\') sevColor = \'#eab308\'\r\n'
    b'              return (\r\n'
    b'                <div key={i.id} className={`${s.incidentSlide} ${isActive ? s.incidentSlideActive : \'\'}`}>\r\n'
    b'                  <div className={s.slideHeader} onClick={() => setExpandedSlide(prev => prev === i.id ? null : i.id)}>\r\n'
    b'                    <span className={s.slideSeverityDot} style={{ background: sevColor }} />\r\n'
    b'                    <div className={s.slideHeaderText}>\r\n'
    b'                      <div className={s.slideIncidentName}>{i.name}</div>\r\n'
    b'                      <div className={s.slideIncidentMeta}>{i.type} \xc2\xb7 {i.region} \xc2\xb7 {i.periodLabel || i.period}</div>\r\n'
    b'                    </div>\r\n'
    b'                    <span className={s.slideRiskBadge} style={{ color: sevColor }}>{i.risk}</span>\r\n'
    b'                    <ChevronDown size={12} className={`${s.slideChevron} ${isOpen ? s.slideChevronOpen : \'\'}`} />\r\n'
    b'                  </div>\r\n'
    b'                  <div className={`${s.slideBody} ${isOpen ? s.slideBodyOpen : \'\'}`}>\r\n'
    b'                    <div className={s.slideBodyInner}>\r\n'
    b'                      <div className={s.slideKpiRow}>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Loss</span>\r\n'
    b'                          <span className={s.slideKpiVal} style={{ color: \'#ef4444\' }}>${i.financialLoss.toLocaleString()}</span>\r\n'
    b'                        </div>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Orders</span>\r\n'
    b'                          <span className={s.slideKpiVal}>{i.affectedOrders.toLocaleString()}</span>\r\n'
    b'                        </div>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Conf</span>\r\n'
    b'                          <span className={s.slideKpiVal} style={{ color: \'#3b82f6\' }}>{i.confidence}</span>\r\n'
    b'                        </div>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Delay</span>\r\n'
    b'                          <span className={s.slideKpiVal}>{i.expectedDelay}d</span>\r\n'
    b'                        </div>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Customers</span>\r\n'
    b'                          <span className={s.slideKpiVal}>{i.customers.toLocaleString()}</span>\r\n'
    b'                        </div>\r\n'
    b'                        <div className={s.slideKpiBox}>\r\n'
    b'                          <span className={s.slideKpiLabel}>Drop</span>\r\n'
    b'                          <span className={s.slideKpiVal} style={{ color: \'#f97316\' }}>-{i.forecastDrop}%</span>\r\n'
    b'                        </div>\r\n'
    b'                      </div>\r\n'
    b'                      <div className={s.slideTagRow}>\r\n'
    b'                        <span className={`${s.tag} ${i.status === \'Resolved\' ? s.tagGreen : s.tagAmber}`}>{i.status}</span>\r\n'
    b'                        <span className={s.tag} style={{ background: `${sevColor}15`, color: sevColor, border: `1px solid ${sevColor}30` }}>{i.severity}</span>\r\n'
    b'                        {i._fromForecast && (\r\n'
    b'                          <span style={{ fontSize: \'8px\', background: \'#dbeafe\', color: \'#1d4ed8\', padding: \'2px 6px\', borderRadius: 8, fontWeight: 800, border: \'1px solid #93c5fd\' }}>\xf0\x9f\x93\x88 Forecast</span>\r\n'
    b'                        )}\r\n'
    b'                      </div>\r\n'
    b'                      <button\r\n'
    b'                        className={`${s.slideSelectBtn} ${isActive ? s.slideSelectBtnActive : \'\'}`}\r\n'
    b'                        onClick={() => handleIncidentSelect(i.id, i.type)}\r\n'
    b'                      >\r\n'
    b'                        {isActive ? \'\xe2\x9c\x93 Currently Investigating\' : \'Open Investigation \xe2\x86\x92\'}\r\n'
    b'                      </button>\r\n'
    b'                    </div>\r\n'
    b'                  </div>\r\n'
    b'                </div>\r\n'
    b'              )\r\n'
    b'            })}\r\n'
    b'          </div>\r\n'
    b'        </aside>\r\n'
    b'\r\n'
    b'        {/* \xe7\xac\x8f\xe2\x95\x90\xe6\xa5\xb3 CENTER COLUMN'
)

raw = raw[:i_start] + NEW + raw[i_end + len(END):]

with open(path, 'wb') as f:
    f.write(raw)
print('DONE', len(raw), file=sys.stderr)
