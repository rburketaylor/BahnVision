import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRoutePlanner } from '../../hooks/useRoutePlanner'
import { apiClient } from '../../services/api'
import type { RoutePlanParams } from '../../types/api'

vi.mock('../../services/api', () => ({
  apiClient: {
    planRoute: vi.fn(),
  },
}))

const mockPlanRoute = vi.mocked(apiClient.planRoute)

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useRoutePlanner', () => {
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

  it('fetches routes with expected caching options', async () => {
    const params: RoutePlanParams = {
      origin: 'de:1',
      destination: 'de:2',
    }
    mockPlanRoute.mockResolvedValue({ data: { routes: [] } })

    renderHook(() => useRoutePlanner({ params }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(mockPlanRoute).toHaveBeenCalledWith(params)
    })

    const query = queryClient.getQueryCache().find(['route-plan', params])
    expect(query?.queryKey).toEqual(['route-plan', params])
    expect(query?.options.staleTime).toBe(120_000)
  })

  it('respects enabled flag', () => {
    const params: RoutePlanParams = {
      origin: 'de:1',
      destination: 'de:2',
    }

    const { result } = renderHook(() => useRoutePlanner({ params, enabled: false }), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockPlanRoute).not.toHaveBeenCalled()
  })
})
