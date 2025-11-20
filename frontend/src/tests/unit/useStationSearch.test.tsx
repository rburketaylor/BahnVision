import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useStationSearch } from '../../hooks/useStationSearch'
import { apiClient } from '../../services/api'
import type { StationSearchParams } from '../../types/api'

vi.mock('../../services/api', () => ({
  apiClient: {
    searchStations: vi.fn(),
  },
}))

const mockSearchStations = vi.mocked(apiClient.searchStations)

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
    const params: StationSearchParams = { query: '', limit: 5 }

    const { result } = renderHook(() => useStationSearch(params, true), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockSearchStations).not.toHaveBeenCalled()

    const disabledHook = renderHook(() => useStationSearch({ query: 'munich', limit: 5 }, false), {
      wrapper: createWrapper(queryClient),
    })

    expect(disabledHook.result.current.isFetching).toBe(false)
    expect(mockSearchStations).not.toHaveBeenCalled()
  })

  it('enables retries with custom backoff and cache timings', async () => {
    const params: StationSearchParams = { query: 'marien', limit: 3 }
    mockSearchStations.mockResolvedValue({ data: { results: [] } })

    renderHook(() => useStationSearch(params), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(mockSearchStations).toHaveBeenCalledWith(params)
    })

    const query = queryClient.getQueryCache().find(['stations', 'search', params])
    expect(query?.options.staleTime).toBe(300_000)
    expect(query?.options.gcTime).toBe(600_000)
    expect(query?.options.refetchOnWindowFocus).toBe(false)

    const retryFn = query?.options.retry as (
      failureCount: number,
      error: Error & { statusCode?: number }
    ) => boolean

    const rateLimitError = Object.assign(new Error('rate limited'), { statusCode: 429 })
    expect(retryFn(0, rateLimitError)).toBe(false)

    const clientError = Object.assign(new Error('bad request'), { statusCode: 404 })
    expect(retryFn(0, clientError)).toBe(false)

    const serverError = Object.assign(new Error('server'), { statusCode: 500 })
    expect(retryFn(1, serverError)).toBe(true)
    expect(retryFn(2, serverError)).toBe(false)

    const retryDelay = query?.options.retryDelay as (attempt: number) => number
    expect(retryDelay(0)).toBe(1000)
    expect(retryDelay(1)).toBe(2000)
    expect(retryDelay(5)).toBe(3000)
  })
})
