import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MonitoringPage from '../../../pages/MonitoringPage'
import { useHealth } from '../../../hooks/useHealth'
import { apiClient } from '../../../services/api'

vi.mock('../../../hooks/useHealth', () => ({
  useHealth: vi.fn(),
}))

vi.mock('../../../services/api', () => ({
  apiClient: {
    getMetrics: vi.fn(),
    getIngestionStatus: vi.fn(),
  },
}))

const mockUseHealth = vi.mocked(useHealth)
const mockGetMetrics = vi.mocked(apiClient.getMetrics)
const mockGetIngestionStatus = vi.mocked(apiClient.getIngestionStatus)

describe('MonitoringPage', () => {
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

    mockGetMetrics.mockResolvedValue('')
    mockGetIngestionStatus.mockResolvedValue({
      data: {
        gtfs_feed: {
          feed_id: 'test-feed',
          feed_url: 'https://example.com/gtfs.zip',
          downloaded_at: '2025-01-01T00:00:00Z',
          feed_start_date: '2025-01-01',
          feed_end_date: '2025-12-31',
          stop_count: 1000,
          route_count: 50,
          trip_count: 5000,
          is_expired: false,
        },
        gtfs_rt_harvester: {
          is_running: true,
          last_harvest_at: '2025-01-01T12:00:00Z',
          stations_updated_last_harvest: 100,
          total_stats_records: 10000,
        },
      },
    })
  })

  it('renders page header', async () => {
    render(<MonitoringPage />)

    await expect(screen.getByRole('heading', { name: 'System Monitoring' })).toBeVisible()
  })

  it('displays tab navigation', async () => {
    render(<MonitoringPage />)

    expect(screen.getByRole('button', { name: /Overview/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ingestion/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Performance/ })).toBeInTheDocument()
  })

  it('switches to Ingestion tab when clicked', async () => {
    render(<MonitoringPage />)

    const user = userEvent.setup()
    const ingestionTab = screen.getByRole('button', { name: /Ingestion/ })

    await user.click(ingestionTab)

    // Wait for ingestion content to load
    await waitFor(() => {
      expect(screen.getByText('GTFS Static Feed')).toBeInTheDocument()
    })
  })

  it('switches to Performance tab when clicked', async () => {
    mockGetMetrics.mockResolvedValue(
      [
        'bahnvision_cache_events_total{cache="transit_departures",event="hit"} 80',
        'bahnvision_cache_events_total{cache="transit_departures",event="miss"} 20',
        'bahnvision_transit_requests_total 100',
      ].join('\n')
    )

    render(<MonitoringPage />)

    const user = userEvent.setup()
    const performanceTab = screen.getByRole('button', { name: /Performance/ })

    await user.click(performanceTab)

    // Wait for performance content to load
    await waitFor(() => {
      expect(screen.getByText('Cache Performance')).toBeInTheDocument()
    })
  })

  it('shows Overview tab by default', async () => {
    render(<MonitoringPage />)

    // Overview tab content should be visible by default
    await waitFor(() => {
      expect(screen.getByText(/All Systems Operational|System Issues/)).toBeInTheDocument()
    })
  })
})
