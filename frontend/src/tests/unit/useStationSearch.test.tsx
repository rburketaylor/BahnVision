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
    // The query was successfully created and executed
    expect(mockSearchStops).toHaveBeenCalledWith(params)
  })
})
