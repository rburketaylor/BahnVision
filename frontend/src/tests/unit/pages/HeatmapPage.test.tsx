/// <reference types="@testing-library/jest-dom/vitest" />
import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ThemeProvider } from '../../../contexts/ThemeContext'
import HeatmapPage from '../../../pages/HeatmapPage'
import { useHeatmapOverview } from '../../../hooks/useHeatmapOverview'
import { useStationStats } from '../../../hooks/useStationStats'
import type { TransitStop } from '../../../types/gtfs'

vi.mock('../../../hooks/useHeatmapOverview', () => ({
  useHeatmapOverview: vi.fn(),
}))

vi.mock('../../../hooks/useStationStats', () => ({
  useStationStats: vi.fn(),
}))

let lastMapProps: { overlay?: ReactNode; focusRequest?: unknown } | null = null

vi.mock('../../../components/heatmap/MapLibreHeatmap', () => ({
  MapLibreHeatmap: (props: { overlay?: ReactNode; focusRequest?: unknown }) => {
    lastMapProps = props
    return <div data-testid="mock-heatmap">{props.overlay}</div>
  },
}))

const mockStop: TransitStop = {
  id: 'stop-123',
  name: 'Test Stop',
  latitude: 52.5,
  longitude: 13.4,
  zone_id: null,
  wheelchair_boarding: 0,
}

vi.mock('../../../components/heatmap', async () => {
  const actual = await vi.importActual<typeof import('../../../components/heatmap')>(
    '../../../components/heatmap'
  )
  return {
    ...actual,
    HeatmapSearchOverlay: ({
      onStationSelect,
    }: {
      onStationSelect?: (stop: TransitStop) => void
    }) => (
      <button
        type="button"
        data-testid="heatmap-search"
        onClick={() => onStationSelect?.(mockStop)}
      >
        Select station
      </button>
    ),
    HeatmapControls: () => <div data-testid="heatmap-controls" />,
    HeatmapLegend: () => <div data-testid="heatmap-legend" />,
    HeatmapStats: () => <div data-testid="heatmap-stats" />,
  }
})

const mockUseHeatmapOverview = vi.mocked(useHeatmapOverview)
const mockUseStationStats = vi.mocked(useStationStats)

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter>
          <HeatmapPage />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

describe('HeatmapPage', () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    lastMapProps = null
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }))

    localStorage.clear()
    mockUseHeatmapOverview.mockReturnValue({
      data: {
        time_range: { from: '2025-01-01T00:00:00Z', to: '2025-01-02T00:00:00Z' },
        points: [],
        summary: {
          total_stations: 0,
          total_departures: 0,
          total_cancellations: 0,
          overall_cancellation_rate: 0,
          most_affected_station: null,
          most_affected_line: null,
        },
        total_impacted_stations: 0,
        last_updated_at: '2025-01-01T00:00:00Z',
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useHeatmapOverview>)

    mockUseStationStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useStationStats>)
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it('restores controls state from localStorage', async () => {
    localStorage.setItem('bahnvision-heatmap-controls-open-v1', '0')

    renderPage()
    await screen.findByTestId('mock-heatmap')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Heatmap controls')).not.toBeInTheDocument()
  })

  it('defaults to live time range', async () => {
    renderPage()
    await screen.findByTestId('mock-heatmap')

    const params = mockUseHeatmapOverview.mock.calls[0]?.[0]
    expect(params?.time_range).toBe('live')
  })

  it('toggles controls with keyboard shortcuts', async () => {
    renderPage()
    await screen.findByTestId('mock-heatmap')

    expect(screen.getByLabelText('Heatmap controls')).toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'c' })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })

    fireEvent.keyDown(window, { key: 'c' })
    await waitFor(() => {
      expect(screen.getByLabelText('Heatmap controls')).toBeInTheDocument()
    })

    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })
  })

  it('shows error state and allows refresh', async () => {
    const refetch = vi.fn()
    mockUseHeatmapOverview.mockReturnValue({
      data: {
        time_range: { from: '2025-01-01T00:00:00Z', to: '2025-01-02T00:00:00Z' },
        points: [],
        summary: {
          total_stations: 0,
          total_departures: 0,
          total_cancellations: 0,
          overall_cancellation_rate: 0,
          most_affected_station: null,
          most_affected_line: null,
        },
        total_impacted_stations: 0,
        last_updated_at: '2025-01-01T00:00:00Z',
      },
      isLoading: false,
      error: new Error('Boom'),
      refetch,
    } as unknown as ReturnType<typeof useHeatmapOverview>)

    renderPage()
    await screen.findByTestId('mock-heatmap')

    expect(screen.getByText('Failed to load heatmap data')).toBeInTheDocument()
    expect(screen.getByText('Boom')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /refresh heatmap data/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows no data message when points are empty', async () => {
    mockUseHeatmapOverview.mockReturnValue({
      data: {
        time_range: { from: '2025-01-01T00:00:00Z', to: '2025-01-02T00:00:00Z' },
        points: [],
        summary: {
          total_stations: 0,
          total_departures: 0,
          total_cancellations: 0,
          overall_cancellation_rate: 0,
          most_affected_station: null,
          most_affected_line: null,
        },
        total_impacted_stations: 0,
        last_updated_at: '2025-01-01T00:00:00Z',
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useHeatmapOverview>)

    renderPage()
    await screen.findByTestId('mock-heatmap')

    expect(screen.getByText('No data available yet')).toBeInTheDocument()
  })

  it('creates a focus request when selecting a station in search overlay', async () => {
    renderPage()
    await screen.findByTestId('mock-heatmap')

    fireEvent.click(screen.getByTestId('heatmap-search'))

    expect(lastMapProps?.focusRequest).toEqual(
      expect.objectContaining({
        stopId: mockStop.id,
        lat: mockStop.latitude,
        lon: mockStop.longitude,
        source: 'search',
      })
    )
  })
})
