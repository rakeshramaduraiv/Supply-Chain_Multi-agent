/**
 * DataCoverageBadge.jsx
 *
 * Shows the active data coverage: base period range, total records,
 * and how many periods have been uploaded.
 * Example: "2015-01 to 2017-09 · 171,962 records · 1 period uploaded"
 *
 * A user must never have to guess whether their upload took effect.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Database } from 'lucide-react'

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString()
}

export default function DataCoverageBadge({ style }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['datasetCoverage'],
    queryFn: () => api.getDatasetCoverage().then(r => r.data),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  })

  if (isLoading) {
    return (
      <span style={{ fontSize: 11, color: '#888', ...style }}>
        Loading coverage…
      </span>
    )
  }

  if (isError || !data) {
    return (
      <span style={{ fontSize: 11, color: '#f59e0b', ...style }}>
        Coverage unavailable
      </span>
    )
  }

  const baseStart = data.base_period_start?.slice(0, 7) ?? '—'
  const latestDate = data.latest_date?.slice(0, 7) ?? data.base_period_end?.slice(0, 7) ?? '—'
  const total = fmt(data.combined_total)
  const nPeriods = data.increment_count ?? 0
  const uploadLabel = nPeriods === 0
    ? 'base only'
    : nPeriods === 1
      ? '1 period uploaded'
      : `${nPeriods} periods uploaded`

  const color = nPeriods > 0 ? '#00b894' : '#74b9ff'

  const tooltip = nPeriods === 0
    ? 'No actuals uploaded yet. Upload a CSV to extend the dataset beyond the training window.'
    : `Base: ${data.base_period_start?.slice(0,7)} – ${data.base_period_end?.slice(0,7)} (${fmt(data.base_row_count)} rows)\n` +
      data.increments.map(i => `  + ${i.period}: ${fmt(i.rows)} rows`).join('\n') +
      `\nCombined: ${total} rows`

  return (
    <span
      title={tooltip}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 9px',
        borderRadius: 6,
        border: `1px solid ${color}40`,
        background: `${color}12`,
        fontSize: 10,
        fontWeight: 700,
        color,
        cursor: 'help',
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      <Database size={11} />
      {baseStart} to {latestDate} · {total} records · {uploadLabel}
    </span>
  )
}
