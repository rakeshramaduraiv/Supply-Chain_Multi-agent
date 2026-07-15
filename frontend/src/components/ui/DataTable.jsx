import { useState, useMemo } from 'react'

export default function DataTable({ columns = [], data = [], loading, emptyMessage }) {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      const cmp = typeof av === 'number' ? av - bv : String(av || '').localeCompare(String(bv || ''))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  if (loading) {
    return (
      <div className="table-wrap">
        <table>
          <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>{columns.map(c => <td key={c.key}><div className="skeleton" style={{ height: '12px', width: '70%' }} /></td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (!data.length) {
    return <div style={{ textAlign: 'center', padding: '24px', fontSize: '12px', color: 'var(--tm)' }}>{emptyMessage || 'No data'}</div>
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(c => (
              <th key={c.key} className={c.sortable ? 'sort' : ''} onClick={c.sortable ? () => handleSort(c.key) : undefined}>
                {c.label}{sortKey === c.key && (sortDir === 'asc' ? ' ↑' : ' ↓')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={row.id || i}>
              {columns.map(c => (
                <td key={c.key}>{c.render ? c.render(row[c.key], row) : row[c.key] ?? '—'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
