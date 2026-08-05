# -*- coding: utf-8 -*-
path = 'frontend/src/pages/ForecastPage.jsx'
src = open(path, 'rb').read().decode('utf-8')

S = '\r\n\r\n\r\n'  # triple CRLF separator

# Find start and end of the useMemo block
start_anchor = '  const errorDiagnostics = useMemo(() => {'
end_anchor   = '  }, [cycleUploadResult, errorDiagQuery.data, categoryForecasts])'

start_idx = src.find(start_anchor)
end_idx   = src.find(end_anchor)

assert start_idx >= 0, 'start not found'
assert end_idx   >= 0, 'end not found'

end_idx += len(end_anchor)

new_block = (
    '  // Error Diagnostics: after upload uses real backend model predictions vs real actuals.' + S +
    '  // Before upload shows forecast-only predictions with actual column empty.' + S +
    '  const errorDiagnostics = useMemo(() => {' + S +
    '    const apiDiag = errorDiagQuery.data?.diagnostics || []' + S +
    '    if (cycleActualsUploaded && apiDiag.length > 0) {' + S +
    '      return apiDiag.map(d => {' + S +
    '        const pred = d.predicted_demand ?? 0' + S +
    '        const act  = d.actual_demand ?? 0' + S +
    '        const diff = act - pred' + S +
    '        const pct  = pred > 0 ? ((diff / pred) * 100).toFixed(1) : \'0.0\'' + S +
    '        return {' + S +
    '          category:          `${d.category} (${d.region})`,' + S +
    '          predicted:         `${Number(pred).toLocaleString()} units`,' + S +
    '          actual:            `${Number(act).toLocaleString()} units`,' + S +
    '          diff:              `${diff >= 0 ? \'+\' : \'\'}${diff.toFixed(0)} (${pct}%)`,' + S +
    '          reason:            d.reason || \'Deviation from forecast baseline\',' + S +
    '          responsible_agent: d.responsible_agent || \'Demand Agent\',' + S +
    '          root_cause:        d.root_cause || \'Variance in actual vs predicted demand\',' + S +
    '        }' + S +
    '      })' + S +
    '    }' + S +
    '    const forecastCats = categoryForecasts.length > 0 ? categoryForecasts.slice(0, 6) : [' + S +
    '      { category: \'Apparel\',     region: \'Western Europe\',  predicted_demand: 2120 },' + S +
    '      { category: \'Electronics\', region: \'Central America\', predicted_demand: 1840 },' + S +
    '      { category: \'Footwear\',    region: \'South America\',   predicted_demand: 1560 },' + S +
    '      { category: \'Sports\',      region: \'North America\',   predicted_demand: 2340 },' + S +
    '      { category: \'Furniture\',   region: \'Eastern Europe\',  predicted_demand: 980  },' + S +
    '      { category: \'Technology\',  region: \'Pacific Asia\',    predicted_demand: 1720 },' + S +
    '    ]' + S +
    '    return forecastCats.map((cat, idx) => ({' + S +
    '      category:          `${cat.category || \'Category\'} (${cat.region || \'Region\'})`,' + S +
    '      predicted:         `${(cat.predicted_demand || 2120).toLocaleString()} units`,' + S +
    '      actual:            \'\\u2014\',' + S +
    '      diff:              \'\\u2014\',' + S +
    '      reason:            \'Ingest actuals in Step 2 to see real deviation\',' + S +
    '      responsible_agent: [\'Logistics Agent\', \'Inventory Agent\', \'Supplier Agent\', \'Demand Agent\'][idx % 4],' + S +
    '      root_cause:        \'Awaiting actual data ingestion for this period\',' + S +
    '    }))' + S +
    '  }, [cycleActualsUploaded, errorDiagQuery.data, categoryForecasts])'
)

src = src[:start_idx] + new_block + src[end_idx:]

open(path, 'wb').write(src.encode('utf-8'))
open('_p.txt', 'w').write('DONE\n')
