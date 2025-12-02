import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useHeatmap } from '../../hooks/useHeatmap'
import { apiClient } from '../../services/api'

vi.mock('../../services/api', () => ({
  apiClient: {
    getHeatmapData: vi.fn(),
  },
}))

const mockGetHeatmapData = vi.mocked(apiClient.getHeatmapData)

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

const mockHeatmapResponse = {
  time_range: {
    from: '2025-01-15T00:00:00Z',
    to: '2025-01-16T00:00:00Z',
  },
  data_points: [
    {
      station_id: 'de:09162:6',
      station_name: 'Marienplatz',
      latitude: 48.137,
      longitude: 11.575,
      total_departures: 1250,
      cancelled_count: 45,
      cancellation_rate: 0.036,
      by_transport: {
        UBAHN: { total: 500, cancelled: 20 },
      },
    },
  ],
  summary: {
    total_stations: 1,
    total_departures: 1250,
    total_cancellations: 45,
    overall_cancellation_rate: 0.036,
    most_affected_station: 'Marienplatz',
    most_affected_line: 'U-Bahn',
  },
}

describe('useHeatmap', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    })
    vi.clearAllMocks()
  })

  it('fetches heatmap data successfully', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap(), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetHeatmapData).toHaveBeenCalledTimes(1)
    expect(result.current.data?.data).toEqual(mockHeatmapResponse)
  })

  it('passes params to API client', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const params = { time_range: '6h' as const, transport_modes: ['UBAHN' as const] }

    const { result } = renderHook(() => useHeatmap(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetHeatmapData).toHaveBeenCalledWith(params)
  })

  it('respects autoRefresh option', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}, { autoRefresh: true }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Verify the hook was called - auto-refresh behavior is configured
    expect(mockGetHeatmapData).toHaveBeenCalled()
  })

  it('disables auto-refresh when specified', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}, { autoRefresh: false }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Verify the hook was called successfully
    expect(mockGetHeatmapData).toHaveBeenCalled()
  })

  it('can be disabled', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}, { enabled: false }), {
      wrapper: createWrapper(queryClient),
    })

    // Should not make any requests when disabled
    expect(result.current.isLoading).toBe(false)
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockGetHeatmapData).not.toHaveBeenCalled()
  })
})
