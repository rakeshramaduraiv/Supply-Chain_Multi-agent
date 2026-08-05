import re

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\ForecastPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# ── 1. Replace the entire handleIngestSyntheticMonth function ──
old_fn_start = '  const handleIngestSyntheticMonth = (periodStr) => {'
old_fn_end   = '  }\n\n  // ── Derived Data from Backend'

start_idx = src.index(old_fn_start)
end_idx   = src.index(old_fn_end) + len('  }')

new_fn = r"""  // Parse CSV text into array-of-objects
  const parseCSV = (text) => {
    const lines = text.trim().split(/\r?\n/)
    if (lines.length < 2) return []
    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
    return lines.slice(1).map(line => {
      const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
      const row = {}
      headers.forEach((h, i) => { row[h] = vals[i] ?? '' })
      return row
    })
  }

  const handleIngestSyntheticMonth = (periodStr, csvFile = null) => {
    clearLog(2)
    appendLog(2, `\u{1F4C2} Loading actuals for period ${periodStr}\u2026`)
    appendLog(2, `\u{1F504} Running 12-stage ECLE validation pipeline\u2026`)
    setIsIngestingActuals(true)

    const agentMap = ['Logistics Agent', 'Demand Agent', 'Inventory Agent', 'Supplier Agent', 'Logistics Agent', 'Demand Agent']

    const processRows = (rows) => {
      const cats = categoryForecasts.length > 0
        ? categoryForecasts.slice(0, 6)
        : [
            { category: 'Apparel',     region: 'Western Europe',   predicted_demand: 2120 },
            { category: 'Electronics', region: 'Central America',  predicted_demand: 1840 },
            { category: 'Footwear',    region: 'South America',    predicted_demand: 1560 },
            { category: 'Sports',      region: 'North America',    predicted_demand: 2340 },
            { category: 'Furniture',   region: 'Eastern Europe',   predicted_demand: 980  },
            { category: 'Technology',  region: 'Pacific Asia',     predicted_demand: 1720 },
          ]

      // Build actual lookup from CSV rows grouped by Category Name x Order Region
      const actualMap = {}
      if (rows.length > 0) {
        const colKeys = Object.keys(rows[0])
        const findCol = (...candidates) =>
          colKeys.find(k => candidates.some(c => k.toLowerCase().replace(/[^a-z]/g, '').includes(c.toLowerCase().replace(/[^a-z]/g, '')))) || null
        const catCol  = findCol('Category Name', 'categoryname', 'category')
        const regCol  = findCol('Order Region', 'orderregion', 'region')
        const qtyCol  = findCol('Order Item Quantity', 'orderitemquantity', 'quantity', 'qty')
        const lateCol = findCol('Late_delivery_risk', 'latedeliveryrisk', 'late')

        if (catCol && regCol) {
          rows.forEach(row => {
            const cat = (row[catCol] || '').trim()
            const reg = (row[regCol] || '').trim()
            if (!cat || !reg) return
            const key = cat + '||' + reg
            if (!actualMap[key]) actualMap[key] = { count: 0, qty: 0, late: 0 }
            actualMap[key].count += 1
            actualMap[key].qty   += qtyCol  ? (parseFloat(row[qtyCol])  || 0) : 1
            actualMap[key].late  += lateCol ? (parseFloat(row[lateCol]) || 0) : 0
          })
        }
      }

      const hasRealData = Object.keys(actualMap).length > 0

      const comparison_records = cats.map((cat, i) => {
        const pred  = Math.round(cat.predicted_demand || 2000)
        const key   = cat.category + '||' + cat.region
        const entry = actualMap[key]

        let act, reason, root_cause
        if (entry) {
          act = Math.round(entry.qty > 0 ? entry.qty : entry.count)
          const lateRate = entry.count > 0 ? entry.late / entry.count : 0
          reason = lateRate > 0.5
            ? `High late-delivery rate (${(lateRate * 100).toFixed(1)}%) in uploaded actuals`
            : `Actual demand recorded from uploaded CSV \u2014 ${entry.count} rows matched`
          root_cause = `Actual orders: ${act.toLocaleString()} vs forecast: ${pred.toLocaleString()} \u2014 ${cat.category} \u00b7 ${cat.region}`
        } else if (hasRealData) {
          const totalQty = Object.values(actualMap).reduce((s, e) => s + (e.qty > 0 ? e.qty : e.count), 0)
          act = Math.round(totalQty / cats.length)
          reason = `Category/region not found in uploaded CSV \u2014 proportional estimate used`
          root_cause = `No exact match for ${cat.category} \u00b7 ${cat.region} in uploaded file`
        } else {
          act = null
          reason = 'No CSV data parsed \u2014 check file format'
          root_cause = 'Upload a DataCo-format CSV with Category Name and Order Region columns'
        }

        const devPct = act != null && pred > 0 ? (((act - pred) / pred) * 100).toFixed(1) : null
        return {
          entity_id:         `${cat.category} (${cat.region})`,
          category:          cat.category,
          region:            cat.region,
          predicted_value:   pred,
          actual_value:      act,
          deviation_pct:     devPct,
          responsible_agent: agentMap[i % agentMap.length],
          reason,
          root_cause,
        }
      })

      const validRecs  = comparison_records.filter(r => r.actual_value != null && r.deviation_pct != null)
      const totalPred  = comparison_records.reduce((s, r) => s + r.predicted_value, 0)
      const totalAct   = validRecs.reduce((s, r) => s + r.actual_value, 0)
      const mape       = validRecs.length > 0
        ? validRecs.reduce((s, r) => s + Math.abs(parseFloat(r.deviation_pct)), 0) / validRecs.length
        : 0
      const accuracy   = parseFloat((100 - mape).toFixed(1))
      const within     = validRecs.filter(r => Math.abs(parseFloat(r.deviation_pct)) < 10).length
      const minor      = validRecs.filter(r => { const a = Math.abs(parseFloat(r.deviation_pct)); return a >= 10 && a < 25 }).length
      const major      = validRecs.filter(r => Math.abs(parseFloat(r.deviation_pct)) >= 25).length

      const result = {
        records_loaded:    rows.length || comparison_records.length,
        records_matched:   validRecs.length,
        overall_accuracy:  accuracy,
        mape_val:          parseFloat(mape.toFixed(2)),
        deviation_summary: { within_threshold: within, minor_deviation: minor, major_deviation: major },
        period:            periodStr,
        comparison_records,
        chart_point:       { period: periodStr, actual: totalAct, forecast: totalPred },
      }

      appendLog(2, `\u2705 ${result.records_loaded.toLocaleString()} records \u00b7 ${validRecs.length} matched \u00b7 Accuracy: ${accuracy}% \u00b7 MAPE: ${mape.toFixed(2)}%`, true)
      setCycleUploadResult(result)
      setCycleActualsUploaded(true)
      setIsIngestingActuals(false)
      setCompletedCycles(prev => {
        const filtered = prev.filter(c => c.period !== periodStr)
        return [...filtered, result.chart_point]
      })

      const newIncidents = comparison_records
        .filter(r => r.deviation_pct != null && Math.abs(parseFloat(r.deviation_pct)) > 5)
        .map(r => ({
          id: `forecast_deviation_${periodStr}_${r.category?.toLowerCase().replace(/\s+/g, '_')}`,
          name: `Forecast Deviation: ${r.entity_id}`,
          type: 'Product',
          period: periodStr,
          periodLabel: FORECAST_MONTHS.find(m => m.period === periodStr)?.label || periodStr,
          risk: `${Math.abs(parseFloat(r.deviation_pct)).toFixed(1)}%`,
          riskVal: Math.abs(parseFloat(r.deviation_pct)) / 100,
          severity: Math.abs(parseFloat(r.deviation_pct)) > 8 ? 'High' : 'Medium',
          impact: 'Medium',
          confidence: `${accuracy}%`,
          financialLoss: Math.round(Math.abs((r.predicted_value - (r.actual_value || 0))) * 45),
          affectedOrders: Math.round(Math.abs(r.predicted_value - (r.actual_value || 0))),
          expectedDelay: 0.8,
          region: r.region || 'Global',
          warehouse: 'Zone 1',
          bu: 'Forecasting',
          status: 'Open RCA',
          customers: Math.round(Math.abs(r.predicted_value - (r.actual_value || 0)) * 0.4),
          products: 1,
          forecastDrop: Math.abs(parseFloat(r.deviation_pct)),
          startedTime: `${periodStr}-01 00:00`,
          affectedSupplier: r.responsible_agent || 'Demand Agent',
          affectedWarehouse: 'Warehouse Zone 1',
          businessCriticality: 'Medium Priority',
          graphConfidence: `${accuracy}%`,
          predictionSource: `Forecast Cycle \u2014 ${periodStr}`,
          timeSinceDetection: `Uploaded ${periodStr} Actuals`,
          _fromForecast: true,
        }))

      if (newIncidents.length > 0) {
        const existing = JSON.parse(localStorage.getItem('amasci_forecast_incidents') || '[]')
        const existingFiltered = existing.filter(i => !newIncidents.some(n => n.id === i.id))
        localStorage.setItem('amasci_forecast_incidents', JSON.stringify([...newIncidents, ...existingFiltered]))
        window.dispatchEvent(new CustomEvent('amasci:forecast_incidents_updated'))
      }

      setUploadHistory(prev => [{
        period:    periodStr,
        records:   result.records_loaded,
        status:    'Validated',
        accuracy:  `${accuracy}%`,
        mape:      `${mape.toFixed(2)}%`,
        timestamp: new Date().toLocaleString(),
      }, ...prev])
      toast.success(`Actuals for ${periodStr} ingested \u2014 ${validRecs.length} categories matched`)
      qc.invalidateQueries({ queryKey: ['supplyChain'] })
      setCycleStep(3)
    }

    if (csvFile) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const rows = parseCSV(e.target.result || '')
        appendLog(2, `\u{1F4CA} Parsed ${rows.length} rows from ${csvFile.name}\u2026`)
        processRows(rows)
      }
      reader.onerror = () => {
        appendLog(2, '\u26a0\ufe0f File read error \u2014 processing without CSV data', true)
        processRows([])
      }
      reader.readAsText(csvFile)
    } else {
      setTimeout(() => processRows([]), 1400)
    }
  }"""

src = src[:start_idx] + new_fn + '\n\n' + src[end_idx + 2:]

# ── 2. Pass csvFile to handleIngestSyntheticMonth in onFile handler ──
old_onfile = 'handleIngestSyntheticMonth(cycleMonth)\r\n                }}'
new_onfile = 'handleIngestSyntheticMonth(cycleMonth, file)\r\n                }}'
src = src.replace(old_onfile, new_onfile)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print('DONE')
