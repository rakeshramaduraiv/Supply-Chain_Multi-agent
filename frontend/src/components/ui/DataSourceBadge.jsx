/**
 * DataSourceBadge.jsx
 *
 * Shows data source mode from the backend.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Database } from 'lucide-react'

export default function DataSourceBadge({ style }) {
  const { data } = useQuery({
    queryKey: ['dataSourceMode'],
    queryFn: () => api.getDataSourceMode().then(r => r.data),
    staleTime: 60_000,
  })

  const isReal = data?.use_real_holdout_actuals ?? false
  const label  = isReal
    ? `Real held-out data (${data?.actuals_range ?? ''})`
    : 'Synthetic data'
  const color  = isReal ? '#00b894' : '#f59e0b'

  return (
    <span
      title={isReal
        ? 'Models trained on DataCo dataset. Holdout months are genuine unseen data.'
        : 'Evaluation uses synthetic continuation data.'}
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
        ...style,
      }}
    >
      <Database size={11} />
      {label}
    </span>
  )
}
