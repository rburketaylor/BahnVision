/**
 * Tests for useStationStats hook
 * Validates data fetching for station statistics and trends
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useStationStats, useStationTrends } from '../../hooks/useStationStats'
import { transitApiClient } from '../../services/endpoints/transitApi'

// Mock the transit API client
vi.mock('../../services/endpoints/transitApi', () => ({
  transitApiClient: {
    getStationStats: vi.fn(),
    getStationTrends: vi.fn(),
  },
}))

const mockTransitApiClient = transitApiClient as unknown as {
  getStationStats: ReturnType<typeof vi.fn>
  getStationTrends: ReturnType<typeof vi.fn>
}

const mockStationStats = {
  station_id: 'de:09162:1',
  station_name: 'München Hbf',
  time_range: '24h',
  total_departures: 1000,
  cancelled_count: 50,
  cancellation_rate: 0.05,
  delayed_count: 200,
  delay_rate: 0.2,
  network_avg_cancellation_rate: 0.03,
  network_avg_delay_rate: 0.15,
  performance_score: 85,
  by_transport: [
    {
      transport_type: 'rail',
      display_name: 'Rail',
      total_departures: 500,
      cancelled_count: 25,
      cancellation_rate: 0.05,
      delayed_count: 100,
      delay_rate: 0.2,
    },
  ],
  data_from: '2025-12-17T00:00:00Z',
  data_to: '2025-12-18T00:00:00Z',
}

const mockStationTrends = {
  station_id: 'de:09162:1',
  station_name: 'München Hbf',
  time_range: '24h',
  granularity: 'hourly',
  data_points: [
    {
      timestamp: '2025-12-18T10:00:00Z',
      total_departures: 50,
      cancelled_count: 2,
      cancellation_rate: 0.04,
      delayed_count: 10,
      delay_rate: 0.2,
    },
    {
      timestamp: '2025-12-18T11:00:00Z',
      total_departures: 60,
      cancelled_count: 3,
      cancellation_rate: 0.05,
      delayed_count: 12,
      delay_rate: 0.2,
    },
  ],
  avg_cancellation_rate: 0.045,
  avg_delay_rate: 0.2,
  peak_cancellation_rate: 0.05,
  peak_delay_rate: 0.2,
  data_from: '2025-12-17T00:00:00Z',
  data_to: '2025-12-18T00:00:00Z',
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useStationStats hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches station stats successfully', async () => {
    mockTransitApiClient.getStationStats.mockResolvedValueOnce({
      data: mockStationStats,
    })

    const { result } = renderHook(() => useStationStats('de:09162:1', '24h'), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockStationStats)
    expect(mockTransitApiClient.getStationStats).toHaveBeenCalledWith({
      stop_id: 'de:09162:1',
      time_range: '24h',
    })
  })

  it('handles missing stop_id by not fetching', async () => {
    const { result } = renderHook(() => useStationStats(undefined, '24h'), {
      wrapper: createWrapper(),
    })

    // Should not be loading when disabled
    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toBeUndefined()
    expect(mockTransitApiClient.getStationStats).not.toHaveBeenCalled()
  })

  it('respects enabled option', async () => {
    const { result } = renderHook(() => useStationStats('de:09162:1', '24h', { enabled: false }), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(false)
    expect(mockTransitApiClient.getStationStats).not.toHaveBeenCalled()
  })
})

describe('useStationTrends hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches station trends successfully', async () => {
    mockTransitApiClient.getStationTrends.mockResolvedValueOnce({
      data: mockStationTrends,
    })

    const { result } = renderHook(() => useStationTrends('de:09162:1', '24h', 'hourly'), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockStationTrends)
    expect(mockTransitApiClient.getStationTrends).toHaveBeenCalledWith({
      stop_id: 'de:09162:1',
      time_range: '24h',
      granularity: 'hourly',
    })
  })

  it('supports daily granularity', async () => {
    mockTransitApiClient.getStationTrends.mockResolvedValueOnce({
      data: { ...mockStationTrends, granularity: 'daily' },
    })

    const { result } = renderHook(() => useStationTrends('de:09162:1', '7d', 'daily'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockTransitApiClient.getStationTrends).toHaveBeenCalledWith({
      stop_id: 'de:09162:1',
      time_range: '7d',
      granularity: 'daily',
    })
  })

  it('handles missing stop_id by not fetching', async () => {
    const { result } = renderHook(() => useStationTrends(undefined, '24h', 'hourly'), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toBeUndefined()
    expect(mockTransitApiClient.getStationTrends).not.toHaveBeenCalled()
  })
})
