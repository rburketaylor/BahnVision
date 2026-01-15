import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useHeatmapOverview } from './useHeatmapOverview'
import { apiClient } from '../services/api'
import type { HeatmapOverviewResponse } from '../types/heatmap'

// Mock the API client
vi.mock('../services/api', () => ({
  apiClient: {
    getHeatmapOverview: vi.fn(),
  },
}))

describe('useHeatmapOverview', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()
  })

  it('fetches lightweight overview data', async () => {
    const mockData: HeatmapOverviewResponse = {
      time_range: {
        from: '2024-01-14T00:00:00Z',
        to: '2024-01-14T23:59:59Z',
      },
      points: [{ id: 'stop-1', lat: 52.52, lon: 13.41, i: 0.15, n: 'Berlin Hbf' }],
      summary: {
        total_stations: 1,
        total_departures: 100,
        total_cancellations: 5,
        overall_cancellation_rate: 0.05,
        total_delays: 10,
        overall_delay_rate: 0.1,
        most_affected_station: 'Berlin Hbf',
        most_affected_line: null,
      },
      total_impacted_stations: 1,
    }

    vi.mocked(apiClient.getHeatmapOverview).mockResolvedValue({ data: mockData })

    const { result } = renderHook(() => useHeatmapOverview({ time_range: 'live' }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.points).toHaveLength(1)
    expect(result.current.data?.points[0].id).toBe('stop-1')
  })

  it('validates response structure', async () => {
    // Use type assertion for intentionally invalid mock data
    const invalidData = { points: null } as unknown as HeatmapOverviewResponse
    vi.mocked(apiClient.getHeatmapOverview).mockResolvedValue({ data: invalidData })

    const { result } = renderHook(() => useHeatmapOverview({ time_range: 'live' }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toContain('Invalid')
  })
})
