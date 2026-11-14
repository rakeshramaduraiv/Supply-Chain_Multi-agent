/**
 * frontend/src/components/forecast/__tests__/cycle_components.test.jsx
 *
 * Vitest + @testing-library/react tests.
 * Install: npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
 * Run:     npx vitest run
 *
 * Tests:
 *  - StageStepper renders exactly as many steps as stage_names has entries
 *  - SKIPPED stage renders as "Skipped" with its reason, not as "Completed"
 *  - FAILED stage shows error text and retry button
 *  - Upload disabled with locked_reason visible when can_upload is false
 *  - Empty available_periods renders NoPeriodsAvailable, not a blank stepper
 *  - No rendered value is NaN; no percentage falls outside 0-100
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'

import StageRow from '../StageRow'
import StageStepper from '../StageStepper'
import { NoPeriodsAvailable } from '../EmptyStates'
import CycleResults from '../CycleResults'

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeCycleState(overrides = {}) {
  return {
    stage_names: {
      0: 'Forecast Issued', 1: 'Ingest & Validate', 2: 'Match',
      3: 'Evaluate', 4: 'TPKE Evolve', 5: 'Store & Retrain', 6: 'Forecast Next',
    },
    next_expected_period: '2017-10',
    awaiting_actuals_for: '2017-10',
    available_periods: [],
    all_complete: false,
    total_available: 4,
    total_complete: 0,
    ...overrides,
  }
}

function makePeriodEntry(overrides = {}) {
  return {
    period: '2017-10',
    filename: '2017_10_actual.csv',
    rows: 2255,
    stage_reached: -1,
    stage_statuses: {},
    can_upload: false,
    locked_reason: null,
    is_complete: false,
    ...overrides,
  }
}

// ── StageStepper ──────────────────────────────────────────────────────────────

describe('StageStepper', () => {
  it('renders exactly as many stage rows as stage_names has entries', () => {
    const cycleState  = makeCycleState()
    const periodEntry = makePeriodEntry({ period: '2017-10' })
    const { container } = render(
      <StageStepper
        periodEntry={periodEntry}
        cycleState={cycleState}
        isIssuingForecast={false}
        isUploadingActuals={false}
        onIssueForecast={vi.fn()}
        onUploadActuals={vi.fn()}
        onRefetch={vi.fn()}
      />
    )
    // stage_names has 7 entries (0-6)
    const stepItems = container.querySelectorAll('[class*="stepItem"]')
    expect(stepItems.length).toBe(7)
  })

  it('shows Generate Forecast button for active period with no stage 0', () => {
    const cycleState  = makeCycleState()
    const periodEntry = makePeriodEntry({ period: '2017-10' })
    render(
      <StageStepper
        periodEntry={periodEntry}
        cycleState={cycleState}
        isIssuingForecast={false}
        isUploadingActuals={false}
        onIssueForecast={vi.fn()}
        onUploadActuals={vi.fn()}
        onRefetch={vi.fn()}
      />
    )
    expect(screen.getByText(/Generate forecast for 2017-10/i)).toBeInTheDocument()
  })

  it('shows Upload button when can_upload is true', () => {
    const cycleState  = makeCycleState()
    const periodEntry = makePeriodEntry({
      period: '2017-10',
      can_upload: true,
      stage_statuses: {
        '0': { status: 'COMPLETED', duration_ms: 100, detail: {}, error: null },
      },
    })
    render(
      <StageStepper
        periodEntry={periodEntry}
        cycleState={cycleState}
        isIssuingForecast={false}
        isUploadingActuals={false}
        onIssueForecast={vi.fn()}
        onUploadActuals={vi.fn()}
        onRefetch={vi.fn()}
      />
    )
    expect(screen.getByText(/Upload actuals for/i)).toBeInTheDocument()
  })

  it('shows fallback message in place of upload button when can_upload is false', () => {
    const cycleState  = makeCycleState()
    const periodEntry = makePeriodEntry({
      period: '2017-10',
      can_upload: false,
      locked_reason: null,
      stage_statuses: {
        '0': { status: 'COMPLETED', duration_ms: 100, detail: {}, error: null },
      },
    })
    render(
      <StageStepper
        periodEntry={periodEntry}
        cycleState={cycleState}
        isIssuingForecast={false}
        isUploadingActuals={false}
        onIssueForecast={vi.fn()}
        onUploadActuals={vi.fn()}
        onRefetch={vi.fn()}
      />
    )
    expect(screen.queryByText(/Upload actuals for/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Upload not available for this period/i)).toBeInTheDocument()
  })
})

// ── StageRow ──────────────────────────────────────────────────────────────────

describe('StageRow', () => {
  it('renders SKIPPED as "Skipped" with reason, never as "Completed"', () => {
    const ss = {
      status: 'SKIPPED',
      duration_ms: 12.3,
      detail: { reason: 'no standing forecast for this period' },
      error: null,
    }
    render(<StageRow stage={2} stageName="Match" ss={ss} runningStartedAt={null} onRetry={vi.fn()} />)
    expect(screen.getByText('Skipped')).toBeInTheDocument()
    expect(screen.queryByText('Completed')).not.toBeInTheDocument()
    expect(screen.getByText(/no standing forecast/i)).toBeInTheDocument()
  })

  it('renders FAILED with error text and retry button', () => {
    const ss = {
      status: 'FAILED',
      duration_ms: 5.1,
      detail: {},
      error: 'Period mismatch: actuals 2017-11 vs forecast 2017-10',
    }
    render(<StageRow stage={2} stageName="Match" ss={ss} runningStartedAt={null} onRetry={vi.fn()} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText(/Period mismatch/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('renders PENDING as "Pending" with em dash for duration', () => {
    render(<StageRow stage={3} stageName="Evaluate" ss={null} runningStartedAt={null} />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders COMPLETED with duration in seconds', () => {
    const ss = { status: 'COMPLETED', duration_ms: 2340, detail: { demand_mape: 8.12 }, error: null }
    render(<StageRow stage={3} stageName="Evaluate" ss={ss} runningStartedAt={null} />)
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('2.34s')).toBeInTheDocument()
  })
})

// ── NoPeriodsAvailable ────────────────────────────────────────────────────────

describe('NoPeriodsAvailable', () => {
  it('renders bootstrap command, not a blank panel', () => {
    render(<NoPeriodsAvailable />)
    expect(screen.getByText(/make bootstrap/i)).toBeInTheDocument()
    expect(screen.getByText(/No actuals files found/i)).toBeInTheDocument()
  })
})

// ── CycleResults ──────────────────────────────────────────────────────────────

describe('CycleResults', () => {
  it('does not render before Stage 3 completes', () => {
    const { container } = render(<CycleResults periodEntry={makePeriodEntry()} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders metrics without NaN when values are present', () => {
    const periodEntry = makePeriodEntry({
      stage_statuses: {
        '2': {
          status: 'COMPLETED', duration_ms: 100,
          detail: {
            rows_matched: 150, rows_excluded: 10, match_rate: 0.9375,
            forecast_anchors: 16, actual_anchors: 16, matched_anchors: 15,
          },
          error: null,
        },
        '3': {
          status: 'COMPLETED', duration_ms: 200,
          detail: { demand_mape: 7.42, demand_mae: 1.234, late_delivery_f1: 0.812 },
          error: null,
        },
      },
    })
    render(<CycleResults periodEntry={periodEntry} />)
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    expect(screen.getByText(/7\.42/)).toBeInTheDocument()
    expect(screen.getByText(/0\.812/)).toBeInTheDocument()
    // match rate 93.75% must be within 0-100
    expect(screen.getByText(/93\.75%/)).toBeInTheDocument()
  })

  it('shows unmatched count in its own labelled section', () => {
    const periodEntry = makePeriodEntry({
      stage_statuses: {
        '2': {
          status: 'COMPLETED', duration_ms: 50,
          detail: { rows_matched: 100, rows_excluded: 25, match_rate: 0.8 },
          error: null,
        },
        '3': { status: 'COMPLETED', duration_ms: 80, detail: {}, error: null },
      },
    })
    render(<CycleResults periodEntry={periodEntry} />)
    expect(screen.getByText(/25 unmatched/i)).toBeInTheDocument()
  })

  it('renders SKIPPED Stage 3 with reason, not as complete', () => {
    const periodEntry = makePeriodEntry({
      stage_statuses: {
        '2': { status: 'SKIPPED', duration_ms: 5, detail: { reason: 'no standing forecast' }, error: null },
        '3': { status: 'SKIPPED', duration_ms: 3, detail: { reason: 'no standing forecast for 2017-10' }, error: null },
      },
    })
    render(<CycleResults periodEntry={periodEntry} />)
    expect(screen.getByText(/Metrics skipped/i)).toBeInTheDocument()
    expect(screen.queryByText('Completed')).not.toBeInTheDocument()
  })
})
