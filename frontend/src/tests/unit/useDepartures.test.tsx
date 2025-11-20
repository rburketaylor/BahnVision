import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useDepartures } from '../../hooks/useDepartures'
import { apiClient } from '../../services/api'
import type { DeparturesParams } from '../../types/api'

// Mock the API client
vi.mock('../../services/api', () => ({
  apiClient: {
    getDepartures: vi.fn(),
  },
}))

const mockApiGetDepartures = vi.mocked(apiClient.getDepartures)

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useDepartures', () => {
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

  it('fetches departures with default options', async () => {
    const mockResponse = {
      data: {
        station: { id: 'test', name: 'Test Station', place: 'Munich' },
        departures: [],
      },
    }
    mockApiGetDepartures.mockResolvedValue(mockResponse)

    const params: DeparturesParams = { station: 'test-station' }

    const { result } = renderHook(() => useDepartures(params), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockApiGetDepartures).toHaveBeenCalledWith(params)
    expect(result.current.data).toEqual(mockResponse)
    expect(result.current.isFetching).toBe(false)
  })

  it('enables auto-refresh in live mode', async () => {
    const mockResponse = {
      data: {
        station: { id: 'test', name: 'Test Station', place: 'Munich' },
        departures: [],
      },
    }
    mockApiGetDepartures.mockResolvedValue(mockResponse)

    const params: DeparturesParams = { station: 'test-station' }

    const { result } = renderHook(() => useDepartures(params, { live: true }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // In live mode, refetchInterval should be set (30 seconds)
    const query = queryClient.getQueryCache().find(['departures', params])
    expect(query?.options.refetchInterval).toBe(30000)
    expect(query?.options.staleTime).toBe(30000)
  })

  it('disables auto-refresh in manual mode', async () => {
    const mockResponse = {
      data: {
        station: { id: 'test', name: 'Test Station', place: 'Munich' },
        departures: [],
      },
    }
    mockApiGetDepartures.mockResolvedValue(mockResponse)

    const params: DeparturesParams = { station: 'test-station' }

    const { result } = renderHook(() => useDepartures(params, { live: false }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // In manual mode, refetchInterval should be disabled
    const query = queryClient.getQueryCache().find(['departures', params])
    expect(query?.options.refetchInterval).toBe(false)
    expect(query?.options.staleTime).toBe(0)
  })

  it('uses from parameter when provided', async () => {
    const mockResponse = {
      data: {
        station: { id: 'test', name: 'Test Station', place: 'Munich' },
        departures: [],
      },
    }
    mockApiGetDepartures.mockResolvedValue(mockResponse)

    const params: DeparturesParams = {
      station: 'test-station',
      from: '2025-01-15T10:00:00Z',
      limit: 20,
    }

    const { result } = renderHook(() => useDepartures(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockApiGetDepartures).toHaveBeenCalledWith(params)
  })

  it('handles window_minutes parameter', async () => {
    const mockResponse = {
      data: {
        station: { id: 'test', name: 'Test Station', place: 'Munich' },
        departures: [],
      },
    }
    mockApiGetDepartures.mockResolvedValue(mockResponse)

    const params: DeparturesParams = {
      station: 'test-station',
      window_minutes: 60,
      limit: 15,
    }

    const { result } = renderHook(() => useDepartures(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockApiGetDepartures).toHaveBeenCalledWith(params)
  })

  it('respects enabled parameter', () => {
    const params: DeparturesParams = { station: 'test-station' }

    const { result } = renderHook(() => useDepartures(params, { enabled: false }), {
      wrapper: createWrapper(queryClient),
    })

    // When enabled is false, the query should not fetch
    expect(result.current.isLoading).toBe(false)
    expect(result.current.isFetching).toBe(false)
    expect(mockApiGetDepartures).not.toHaveBeenCalled()
  })

  it('handles API errors', async () => {
    const mockError = new Error('Network error')
    mockApiGetDepartures.mockRejectedValue(mockError)

    const params: DeparturesParams = { station: 'test-station' }

    const { result } = renderHook(() => useDepartures(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBeTruthy()
    expect(mockApiGetDepartures).toHaveBeenCalledWith(params)
  })
})
