import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import type { UseQueryResult } from '@tanstack/react-query'
import { StationPage } from '../../../pages/StationPage'
import { useStationStats, useStationTrends } from '../../../hooks/useStationStats'
import { useDepartures } from '../../../hooks/useDepartures'

vi.mock('../../../hooks/useStationStats', () => ({
  useStationStats: vi.fn(),
  useStationTrends: vi.fn(),
}))

vi.mock('../../../hooks/useDepartures', () => ({
  useDepartures: vi.fn(),
}))

vi.mock('../../../components/features/station/DeparturesBoard', () => ({
  DeparturesBoard: () => <div data-testid="departures-board" />,
}))

const mockUseStationStats = vi.mocked(useStationStats)
const mockUseStationTrends = vi.mocked(useStationTrends)
const mockUseDepartures = vi.mocked(useDepartures)

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderStationPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/station/:stationId"
          element={
            <>
              <LocationDisplay />
              <StationPage />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('StationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockUseStationStats.mockReturnValue({
      data: {
        station_id: 'de:09162:1',
        station_name: 'Central Station',
        time_range: '24h',
        total_departures: 100,
        cancelled_count: 5,
        cancellation_rate: 0.05,
        delayed_count: 10,
        delay_rate: 0.1,
        network_avg_cancellation_rate: 0.03,
        network_avg_delay_rate: 0.08,
        performance_score: 82,
        by_transport: [],
        data_from: '2025-01-01T00:00:00Z',
        data_to: '2025-01-02T00:00:00Z',
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)

    mockUseStationTrends.mockReturnValue({
      data: {
        station_id: 'de:09162:1',
        station_name: 'Central Station',
        time_range: '24h',
        granularity: 'hourly',
        data_points: [],
        avg_cancellation_rate: 0.05,
        avg_delay_rate: 0.1,
        peak_cancellation_rate: 0.08,
        peak_delay_rate: 0.12,
        data_from: '2025-01-01T00:00:00Z',
        data_to: '2025-01-02T00:00:00Z',
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)

    mockUseDepartures.mockReturnValue({
      data: {
        data: {
          stop: {
            id: 'de:09162:1',
            name: 'Central Station',
            latitude: 48.14,
            longitude: 11.558,
            zone_id: 'M',
            wheelchair_boarding: 1,
          },
          departures: [],
          realtime_available: true,
        },
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)
  })

  it('defaults to overview tab and enables stats fetch', () => {
    renderStationPage('/station/de:09162:1')

    const statsCall = mockUseStationStats.mock.calls[0]
    expect(statsCall?.[0]).toBe('de:09162:1')
    expect(statsCall?.[1]).toBe('24h')
    expect(statsCall?.[2]).toMatchObject({ enabled: true })

    const trendsCall = mockUseStationTrends.mock.calls[0]
    expect(trendsCall?.[0]).toBe('de:09162:1')
    expect(trendsCall?.[1]).toBe('24h')
    expect(trendsCall?.[2]).toBe('hourly')
    expect(trendsCall?.[3]).toMatchObject({ enabled: false })

    const departuresCall = mockUseDepartures.mock.calls[0]
    expect(departuresCall?.[0]).toMatchObject({ stop_id: 'de:09162:1', limit: 20 })
    expect(departuresCall?.[1]).toMatchObject({ enabled: false, live: true })
  })

  it('renders transport breakdown when present', () => {
    mockUseStationStats.mockReturnValue({
      data: {
        station_id: 'de:09162:1',
        station_name: 'Central Station',
        time_range: '24h',
        total_departures: 100,
        cancelled_count: 5,
        cancellation_rate: 0.05,
        delayed_count: 10,
        delay_rate: 0.1,
        network_avg_cancellation_rate: 0.03,
        network_avg_delay_rate: 0.08,
        performance_score: 82,
        by_transport: [
          {
            transport_type: 'SBAHN',
            display_name: 'S-Bahn',
            total_departures: 40,
            cancelled_count: 1,
            cancellation_rate: 0.025,
            delayed_count: 5,
            delay_rate: 0.125,
          },
        ],
        data_from: '2025-01-01T00:00:00Z',
        data_to: '2025-01-02T00:00:00Z',
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)

    renderStationPage('/station/de:09162:1')

    expect(screen.getByText('By Transport Type')).toBeInTheDocument()
    expect(screen.getByText('S-Bahn')).toBeInTheDocument()
    expect(screen.getByText('40 deps')).toBeInTheDocument()
    expect(screen.getByText('2.5% cancel')).toBeInTheDocument()
  })

  it('renders empty state when station stats are missing', () => {
    mockUseStationStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)

    mockUseDepartures.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)

    renderStationPage('/station/de:09162:1')

    expect(screen.getByRole('heading', { name: 'Station de:09162:1' })).toBeInTheDocument()
    expect(screen.getByText('No statistics available for this station.')).toBeInTheDocument()
  })

  it('renders stats error state', () => {
    mockUseStationStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Stats unavailable'),
    } as unknown as UseQueryResult)

    renderStationPage('/station/de:09162:1')

    expect(screen.getByText(/Failed to load statistics:/)).toBeInTheDocument()
    expect(screen.getByText(/Stats unavailable/)).toBeInTheDocument()
  })

  it('updates URL and enables schedule tab fetch', async () => {
    const user = userEvent.setup()
    renderStationPage('/station/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Schedule' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=schedule')
    })

    const lastDeparturesCall = mockUseDepartures.mock.calls.at(-1)
    expect(lastDeparturesCall?.[1]).toMatchObject({ enabled: true, live: true })
  })

  it('paginates schedule via offset_minutes when no from time is set', async () => {
    const user = userEvent.setup()
    renderStationPage('/station/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Schedule' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=schedule')
    })

    await user.click(screen.getByRole('button', { name: 'Next →' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('page=1')
      expect(screen.getByTestId('location')).toHaveTextContent('live=false')
    })

    const lastDeparturesCall = mockUseDepartures.mock.calls.at(-1)
    expect(lastDeparturesCall?.[0]).toMatchObject({
      stop_id: 'de:09162:1',
      limit: 20,
      offset_minutes: 30,
    })
    expect(lastDeparturesCall?.[1]).toMatchObject({ enabled: true, live: false })
  })

  it('disables schedule prev button on first page', async () => {
    const user = userEvent.setup()
    renderStationPage('/station/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Schedule' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=schedule')
    })

    expect(screen.getByRole('button', { name: '← Prev' })).toBeDisabled()
  })

  it('paginates schedule via from time when set', async () => {
    const user = userEvent.setup()
    renderStationPage(
      '/station/de:09162:1?tab=schedule&page=0&limit=20&step=60&from=2025-01-01T00:00:00.000Z&live=false'
    )

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=schedule')
      expect(screen.getByTestId('location')).toHaveTextContent('from=2025-01-01T00:00:00.000Z')
    })

    await user.click(screen.getByRole('button', { name: 'Next →' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('from=2025-01-01T01%3A00%3A00.000Z')
      expect(screen.getByTestId('location')).toHaveTextContent('live=false')
    })

    const lastDeparturesCall = mockUseDepartures.mock.calls.at(-1)
    expect(lastDeparturesCall?.[0]).toMatchObject({
      stop_id: 'de:09162:1',
      limit: 20,
      from_time: '2025-01-01T01:00:00.000Z',
    })
    expect(lastDeparturesCall?.[0]).not.toHaveProperty('offset_minutes')
    expect(lastDeparturesCall?.[1]).toMatchObject({ enabled: true, live: false })
  })

  it('clearing schedule time picker returns to live mode', async () => {
    const user = userEvent.setup()
    const { container } = renderStationPage(
      '/station/de:09162:1?tab=schedule&page=0&limit=20&step=60&from=2025-01-01T00:00:00.000Z&live=false'
    )

    const input = container.querySelector('input[type="datetime-local"]')
    expect(input).not.toBeNull()
    await user.clear(input)

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=schedule')
      expect(screen.getByTestId('location')).not.toHaveTextContent('from=')
      expect(screen.getByTestId('location')).toHaveTextContent('live=true')
    })

    const lastDeparturesCall = mockUseDepartures.mock.calls.at(-1)
    expect(lastDeparturesCall?.[0]).toMatchObject({
      stop_id: 'de:09162:1',
      limit: 20,
      offset_minutes: 0,
    })
    expect(lastDeparturesCall?.[1]).toMatchObject({ enabled: true, live: true })
  })

  it('switches to trends tab and updates URL', async () => {
    const user = userEvent.setup()
    renderStationPage('/station/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Trends' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('tab=trends')
    })

    const lastTrendsCall = mockUseStationTrends.mock.calls.at(-1)
    expect(lastTrendsCall?.[3]).toMatchObject({ enabled: true })
  })

  it('renders trends empty state when no data points are available', async () => {
    const user = userEvent.setup()
    renderStationPage('/station/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Trends' }))

    expect(
      await screen.findByText('No trend data available for this time range.')
    ).toBeInTheDocument()
  })
})
