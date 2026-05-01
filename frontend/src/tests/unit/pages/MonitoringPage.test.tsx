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
          import_progress: {
            state: 'idle',
            phase: null,
            message: null,
            percent: null,
            rows_processed: null,
            rows_total: null,
            started_at: null,
            updated_at: null,
            finished_at: null,
            error_type: null,
            error_message: null,
          },
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

    expect(screen.getByRole('tab', { name: /Overview/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Ingestion/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Performance/ })).toBeInTheDocument()
  })

  it('switches to Ingestion tab when clicked', async () => {
    render(<MonitoringPage />)

    const user = userEvent.setup()
    const ingestionTab = screen.getByRole('tab', { name: /Ingestion/ })

    await user.click(ingestionTab)

    // Wait for ingestion content to load
    await waitFor(() => {
      expect(screen.getByText('GTFS Static Feed')).toBeInTheDocument()
    })
  })

  it('shows running GTFS import progress on Ingestion tab', async () => {
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
          import_progress: {
            state: 'running',
            phase: 'copy_stop_times',
            message: 'Copying stop_times.txt',
            percent: 72.4,
            rows_processed: 36200000,
            rows_total: 50000000,
            started_at: '2025-01-01T00:00:00Z',
            updated_at: '2025-01-01T00:05:00Z',
            finished_at: null,
            error_type: null,
            error_message: null,
          },
        },
        gtfs_rt_harvester: {
          is_running: true,
          last_harvest_at: '2025-01-01T12:00:00Z',
          stations_updated_last_harvest: 100,
          total_stats_records: 10000,
        },
      },
    })

    render(<MonitoringPage />)

    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: /Ingestion/ }))

    await waitFor(() => {
      expect(screen.getByText('Import Running')).toBeInTheDocument()
    })
    expect(screen.getByRole('progressbar', { name: /GTFS import progress/ })).toHaveAttribute(
      'aria-valuenow',
      '72.4'
    )
    expect(screen.getByText(/36,200,000 \/ 50,000,000 rows/)).toBeInTheDocument()
  })

  it('shows failed GTFS import details on Ingestion tab', async () => {
    mockGetIngestionStatus.mockResolvedValue({
      data: {
        gtfs_feed: {
          feed_id: null,
          feed_url: null,
          downloaded_at: null,
          feed_start_date: null,
          feed_end_date: null,
          stop_count: 0,
          route_count: 0,
          trip_count: 0,
          is_expired: false,
          import_progress: {
            state: 'failed',
            phase: 'validate',
            message: 'Validating GTFS feed',
            percent: 20,
            rows_processed: null,
            rows_total: null,
            started_at: '2025-01-01T00:00:00Z',
            updated_at: '2025-01-01T00:01:00Z',
            finished_at: '2025-01-01T00:01:00Z',
            error_type: 'GTFSFeedValidationError',
            error_message: 'stops.txt is required and cannot be empty',
          },
        },
        gtfs_rt_harvester: {
          is_running: false,
          last_harvest_at: null,
          stations_updated_last_harvest: 0,
          total_stats_records: 0,
        },
      },
    })

    render(<MonitoringPage />)

    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: /Ingestion/ }))

    await waitFor(() => {
      expect(screen.getByText('Import Failed')).toBeInTheDocument()
    })
    expect(screen.getByText(/GTFSFeedValidationError:/)).toBeInTheDocument()
    expect(screen.getByText(/stops.txt is required/)).toBeInTheDocument()
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
    const performanceTab = screen.getByRole('tab', { name: /Performance/ })

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
