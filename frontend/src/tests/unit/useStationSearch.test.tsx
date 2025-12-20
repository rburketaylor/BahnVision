import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useStationSearch } from '../../hooks/useStationSearch'
import { apiClient } from '../../services/api'
import type { TransitStopSearchParams } from '../../types/gtfs'

vi.mock('../../services/api', () => ({
  apiClient: {
    searchStops: vi.fn(),
  },
}))

const mockSearchStops = vi.mocked(apiClient.searchStops)

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useStationSearch', () => {
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

  it('disables fetching when query text is empty or hook disabled', () => {
    const params: TransitStopSearchParams = { query: '', limit: 5 }

    const { result } = renderHook(() => useStationSearch(params, true), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockSearchStops).not.toHaveBeenCalled()

    const disabledHook = renderHook(() => useStationSearch({ query: 'munich', limit: 5 }, false), {
      wrapper: createWrapper(queryClient),
    })

    expect(disabledHook.result.current.isFetching).toBe(false)
    expect(mockSearchStops).not.toHaveBeenCalled()
  })

  it('enables retries with custom backoff and cache timings', async () => {
    const params: TransitStopSearchParams = { query: 'marien', limit: 3 }
    mockSearchStops.mockResolvedValue({ data: { query: 'marien', results: [] } })

    renderHook(() => useStationSearch(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(mockSearchStops).toHaveBeenCalledWith(params)
    })

    const query = queryClient.getQueryCache().find({ queryKey: ['stops', 'search', params] })
    expect(query).toBeDefined()
    expect(query?.options.staleTime).toBe(5 * 60 * 1000)
    expect(query?.options.gcTime).toBe(10 * 60 * 1000)

    const retryFn = query?.options.retry as (failureCount: number, error: Error) => boolean
    expect(retryFn(0, Object.assign(new Error('Rate limit'), { statusCode: 429 }))).toBe(false)
    expect(retryFn(0, Object.assign(new Error('Bad request'), { statusCode: 400 }))).toBe(false)
    expect(retryFn(0, Object.assign(new Error('Timeout'), { statusCode: 408 }))).toBe(true)
    expect(retryFn(1, new Error('Network error'))).toBe(true)
    expect(retryFn(2, new Error('Network error'))).toBe(false)

    const retryDelayFn = query?.options.retryDelay as (attemptIndex: number) => number
    expect(retryDelayFn(0)).toBe(1000)
    expect(retryDelayFn(1)).toBe(2000)
    expect(retryDelayFn(2)).toBe(3000)
  })
})
