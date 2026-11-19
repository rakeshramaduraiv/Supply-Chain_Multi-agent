import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

const STEP_CALLS = {
  1: (p)       => api.cycle.forecast(p),
  2: (p, file) => api.cycle.actuals(p, file),
  3: (p)       => api.cycle.evaluate(p),
  4: (p)       => api.cycle.graphUpdate(p),
  5: (p)       => api.cycle.rca(p),
  6: (p)       => api.cycle.tpke(p),
  7: (p)       => api.cycle.learn(p),
}

export function useCycleLifecycle() {
  const qc = useQueryClient()
  const stateQ = useQuery({
    queryKey: ['cycleState'],
    queryFn: () => api.cycle.state().then(r => r.data),
    refetchInterval: (q) => {
      const d = q.state.data
      const e = d?.available_periods?.find(p => p.period === d?.next_expected_period)
      const running = e && Object.values(e.steps || {}).some(s => s.status === 'RUNNING')
      return running ? 2000 : 15000
    },
  })
  const s      = stateQ.data || {}
  const period = s.next_expected_period || null
  const entry  = (s.available_periods || []).find(p => p.period === period) || null
  const step   = s.all_complete ? 8 : (entry?.ui_step ?? 1)
  const stepInfo = (n) => entry?.steps?.[String(n)] || null

  const runStep = useMutation({
    mutationFn: ({ n, file }) => STEP_CALLS[n](period, file).then(r => r.data),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['cycleState'] })
      qc.invalidateQueries({ queryKey: ['cycleForecast', period] })
    },
  })
  const close = useMutation({
    mutationFn: () => api.cycle.close(period).then(r => r.data),
    onSuccess: () => qc.invalidateQueries(),          // everything is month-scoped
  })

  return {
    state: s,
    period,
    entry,
    step,
    stepInfo,
    runStep,
    close,
    isLoading: stateQ.isLoading,
    error: stateQ.error,
  }
}
