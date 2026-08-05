# -*- coding: utf-8 -*-
path = 'frontend/src/pages/ForecastPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()
src = raw.decode('utf-8')

SEP = '\r\n\r\n\r\n'

old = (
    "                    // Post-ingestion: predicted + variance only; actual values are in the chart" + SEP +
    "                    <>" + SEP +
    "                      <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>" + SEP +
    "                        Predicted: <strong>{err.predicted}</strong>" + SEP +
    "                      </div>" + SEP +
    "                      <div style={{ fontSize: '11px', fontWeight: 800, color: err.diff.startsWith('+') ? '#d63031' : '#00b894' }}>Variance: {err.diff}</div>" + SEP +
    "                    </>"
)

new = (
    "                    <>" + SEP +
    "                      <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>" + SEP +
    "                        Predicted: <strong>{err.predicted}</strong>" + SEP +
    "                      </div>" + SEP +
    "                      <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>" + SEP +
    "                        Actual: <strong style={{ color: '#00b894' }}>{err.actual}</strong>" + SEP +
    "                      </div>" + SEP +
    "                      <div style={{ fontSize: '11px', fontWeight: 800, color: err.diff.startsWith('+') ? '#d63031' : '#00b894' }}>Variance: {err.diff}</div>" + SEP +
    "                    </>"
)

found = old in src
with open('_p.txt', 'w') as o:
    o.write('found: ' + str(found) + '\n')

if found:
    src = src.replace(old, new)
    with open(path, 'wb') as f:
        f.write(src.encode('utf-8'))
    with open('_p.txt', 'a') as o:
        o.write('DONE\n')
else:
    with open('_p.txt', 'a') as o:
        o.write('NOT FOUND\n')
