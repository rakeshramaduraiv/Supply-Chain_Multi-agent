/**
 * ForecastLifecycle.test.jsx
 *
 * Verifies the Forecast Lifecycle UI steps:
 * 1. When ui_step = 4, visible button is "Update Knowledge Graph for 2017-10" and calls api.cycle.graphUpdate('2017-10')
 * 2. When ui_step = 8, visible button is "Start 2017-11" and calls api.cycle.close('2017-10')
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import ForecastPage from '../../../pages/ForecastPage'
import { api } from '../../../api/client'

vi.mock('../../../api/client', () => ({
  api: {
    cycle: {
      state: vi.fn(),
      forecast: vi.fn(),
      getForecast: vi.fn(),
      actuals: vi.fn(),
      evaluate: vi.fn(),
      graphUpdate: vi.fn(),
      rca: vi.fn(),
      getRca: vi.fn(),
      tpke: vi.fn(),
      learn: vi.fn(),
      close: vi.fn(),
      reset: vi.fn(),
    },
    getDatasetAnalytics: vi.fn().mockResolvedValue({ data: { monthly_trend: [] } }),
    getLatestModels: vi.fn().mockResolvedValue({ data: [] }),
    getGraphStats: vi.fn().mockResolvedValue({ data: { graph_version: 'v1.0' } }),
    getTpkeStatus: vi.fn().mockResolvedValue({ data: { version: 'v1.0' } }),
    getFeatureImportance: vi.fn().mockResolvedValue({ data: { feature_importances: [] } }),
  }
}))

vi.mock('../../../components/ui/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  })
}))

// Mock recharts ResponsiveContainer since jsdom has no layout dimensions
vi.mock('recharts', async () => {
  const original = await vi.importActual('recharts')
  return {
    ...original,
    ResponsiveContainer: ({ children }) => <div style={{ width: 400, height: 200 }}>{children}</div>,
  }
})

function renderWithClient(ui) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ForecastLifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Update Knowledge Graph for 2017-10" when ui_step is 4, clicking it calls api.cycle.graphUpdate', async () => {
    api.cycle.state.mockResolvedValue({
      data: {
        next_expected_period: '2017-10',
        available_periods: [
          {
            period: '2017-10',
            ui_step: 4,
            steps: {
              '1': { status: 'COMPLETED', name: 'Generate Forecast' },
              '2': { status: 'COMPLETED', name: 'Upload Actuals' },
              '3': { status: 'COMPLETED', name: 'Actual vs Predicted' },
            },
          },
          {
            period: '2017-11',
            ui_step: 1,
            steps: {},
          },
        ],
        all_complete: false,
      },
    })
    api.cycle.graphUpdate.mockResolvedValue({
      data: {
        period: '2017-10',
        step: 4,
        status: 'COMPLETED',
        detail: { observations_written: 10, nodes_matched: 8 },
      },
    })

    renderWithClient(<ForecastPage />)

    const btn = await screen.findByRole('button', { name: /Update Knowledge Graph for 2017-10/i })
    expect(btn).toBeInTheDocument()

    fireEvent.click(btn)

    await waitFor(() => {
      expect(api.cycle.graphUpdate).toHaveBeenCalledWith('2017-10')
    })
  })

  it('renders "Start 2017-11" when ui_step is 8, clicking it calls api.cycle.close', async () => {
    api.cycle.state.mockResolvedValue({
      data: {
        next_expected_period: '2017-10',
        available_periods: [
          {
            period: '2017-10',
            ui_step: 8,
            steps: {
              '1': { status: 'COMPLETED' },
              '2': { status: 'COMPLETED' },
              '3': { status: 'COMPLETED' },
              '4': { status: 'COMPLETED' },
              '5': { status: 'COMPLETED' },
              '6': { status: 'COMPLETED' },
              '7': { status: 'COMPLETED' },
            },
          },
          {
            period: '2017-11',
            ui_step: 1,
            steps: {},
          },
        ],
        all_complete: false,
      },
    })
    api.cycle.close.mockResolvedValue({
      data: {
        closed: '2017-10',
        next_period: '2017-11',
        all_complete: false,
      },
    })

    renderWithClient(<ForecastPage />)

    const btn = await screen.findByRole('button', { name: /Start 2017-11/i })
    expect(btn).toBeInTheDocument()

    fireEvent.click(btn)

    await waitFor(() => {
      expect(api.cycle.close).toHaveBeenCalledWith('2017-10')
    })
  })
})
