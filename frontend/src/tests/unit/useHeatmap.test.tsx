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
      delayed_count: 75,
      delay_rate: 0.06,
      by_transport: {
        UBAHN: { total: 500, cancelled: 20, delayed: 30 },
      },
    },
  ],
  summary: {
    total_stations: 1,
    total_departures: 1250,
    total_cancellations: 45,
    overall_cancellation_rate: 0.036,
    total_delays: 75,
    overall_delay_rate: 0.06,
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
    expect(result.current.data).toEqual(mockHeatmapResponse)
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

  it('configures auto-refresh interval when enabled', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}, { autoRefresh: true }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    const query = queryClient.getQueryCache().find({
      queryKey: ['heatmap', 'cancellations', {}],
    })
    expect(query?.options.refetchInterval).toBe(5 * 60 * 1000)
  })

  it('disables auto-refresh when specified', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}, { autoRefresh: false }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    const query = queryClient.getQueryCache().find({
      queryKey: ['heatmap', 'cancellations', {}],
    })
    expect(query?.options.refetchInterval).toBe(false)
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

  it('uses correct query key structure', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const params = { time_range: '24h' as const }

    renderHook(() => useHeatmap(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      const query = queryClient
        .getQueryCache()
        .find({ queryKey: ['heatmap', 'cancellations', params] })
      expect(query).toBeDefined()
    })
  })

  it('uses 5 minute stale time matching backend cache', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap(), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    const query = queryClient.getQueryCache().find({ queryKey: ['heatmap', 'cancellations', {}] })
    expect(query?.options.staleTime).toBe(5 * 60 * 1000)
  })

  it('handles API error gracefully', async () => {
    const mockError = new Error('API Error')
    mockGetHeatmapData.mockRejectedValue(mockError)

    const { result } = renderHook(() => useHeatmap(), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeTruthy()
  })

  it('defaults enabled to true', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}), {
      wrapper: createWrapper(queryClient),
    })

    // Should start loading (enabled by default)
    expect(result.current.isLoading).toBe(true)
  })

  it('defaults autoRefresh to true', async () => {
    mockGetHeatmapData.mockResolvedValue({ data: mockHeatmapResponse })

    const { result } = renderHook(() => useHeatmap({}), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    const query = queryClient.getQueryCache().find({
      queryKey: ['heatmap', 'cancellations', {}],
    })
    expect(query?.options.refetchInterval).toBe(5 * 60 * 1000)
  })
})
