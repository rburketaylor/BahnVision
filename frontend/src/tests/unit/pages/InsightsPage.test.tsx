import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InsightsPage from '../../../pages/InsightsPage'
import { useHealth } from '../../../hooks/useHealth'
import { apiClient } from '../../../services/api'

vi.mock('../../../hooks/useHealth', () => ({
  useHealth: vi.fn(),
}))

vi.mock('../../../services/api', () => ({
  apiClient: {
    getMetrics: vi.fn(),
  },
}))

const mockUseHealth = vi.mocked(useHealth)
const mockGetMetrics = vi.mocked(apiClient.getMetrics)

describe('InsightsPage', () => {
  beforeEach(() => {
    mockUseHealth.mockReturnValue({
      data: {
        data: {
          status: 'ok',
          uptime_seconds: 7200,
          version: '1.0.0',
        },
      },
      isLoading: false,
      error: null,
    } as ReturnType<typeof useHealth>)
  })

  it('parses metrics and shows cache hit rate', async () => {
    mockGetMetrics.mockResolvedValue(
      [
        'bahnvision_cache_events_total{cache="transit_departures",event="hit"} 80',
        'bahnvision_cache_events_total{cache="transit_departures",event="miss"} 20',
        'bahnvision_transit_requests_total 100',
        'bahnvision_transit_request_seconds_bucket{le="0.5"} 0.42',
      ].join('\n')
    )

    render(<InsightsPage />)

    await waitFor(() => {
      expect(screen.getByText('80.0')).toBeInTheDocument()
    })

    expect(screen.getByText('80.0%')).toBeInTheDocument()
    expect(screen.getByText('420')).toBeInTheDocument()
  })

  it('toggles auto-refresh mode', async () => {
    mockGetMetrics.mockResolvedValue('')

    render(<InsightsPage />)

    const user = userEvent.setup()
    const toggleButton = await screen.findByRole('button', { name: /auto-refreshing/i })

    await user.click(toggleButton)

    expect(screen.getByRole('button', { name: /manual refresh/i })).toBeInTheDocument()
  })
})
