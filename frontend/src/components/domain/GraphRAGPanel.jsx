import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../api/client'
import Spinner from '../ui/Spinner'
import EmptyState from '../ui/EmptyState'
import { Search } from 'lucide-react'

const TEMPLATES = [
  'Supplier risk for a category in a region',
  'Stockout root cause for a product',
  'Delivery performance by shipping mode',
  'Seasonal demand impact on a category',
  'Full supply chain path trace',
]

export default function GraphRAGPanel() {
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState(2)

  const mutation = useMutation({
    mutationFn: (q) => api.queryGraphRAG({ query: q, depth }).then(r => r.data),
  })

  const run = () => { if (query.trim()) mutation.mutate(query) }
  const result = mutation.data

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '38% 1fr', gap: '14px' }}>
      <div>
        <div className="section-lbl">Natural language query</div>
        <textarea className="textarea" value={query} onChange={e => setQuery(e.target.value)}
          placeholder="e.g. Why is there a stockout risk for Sporting Goods in Eastern Asia?"
          style={{ fontFamily: 'var(--mono)', fontSize: '12px', marginBottom: '8px' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', fontSize: '11px', color: 'var(--tm)' }}>
          <span>Graph depth</span>
          <input type="range" min={1} max={3} value={depth} onChange={e => setDepth(+e.target.value)}
            style={{ flex: 1 }} />
          <span style={{ color: 'var(--tp)', fontWeight: 500 }}>{depth}</span>
        </div>
        <button className="btn btn-primary btn-full" onClick={run} disabled={!query.trim() || mutation.isPending}>
          Run Query
        </button>
        <div className="section-lbl" style={{ marginTop: '14px' }}>Quick templates</div>
        {TEMPLATES.map((t, i) => (
          <button key={i} className="btn btn-secondary btn-sm btn-full" style={{ marginBottom: '4px', justifyContent: 'flex-start' }}
            onClick={() => setQuery(t)}>
            {t}
          </button>
        ))}
      </div>
      <div>
        {mutation.isPending && <Spinner large text="Analysing knowledge graph..." />}
        {!mutation.isPending && !result && <EmptyState icon={Search} title="Run a query" desc="Ask a question about your supply chain" />}
        {!mutation.isPending && result && (
          <div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--tm)', marginBottom: '10px' }}>
              {result.entities_found || 0} entities · {result.context_nodes || 0} context nodes · {result.time_ms || 0}ms
            </div>
            {result.answer && <div className="grag-section answer"><div className="grag-head">1. Direct Answer</div><div className="grag-text">{result.answer}</div></div>}
            {result.evidence && <div className="grag-section evidence"><div className="grag-head">2. Supporting Evidence</div><div className="grag-text">{result.evidence}</div></div>}
            {result.risks && <div className="grag-section risks"><div className="grag-head">3. Risk Factors</div><div className="grag-text">{result.risks}</div></div>}
            {result.actions && <div className="grag-section action"><div className="grag-head">4. Recommended Action</div><div className="grag-text">{result.actions}</div></div>}
          </div>
        )}
        {mutation.isError && <div className="info-box error">{mutation.error?.message || 'Query failed'}</div>}
      </div>
    </div>
  )
}
