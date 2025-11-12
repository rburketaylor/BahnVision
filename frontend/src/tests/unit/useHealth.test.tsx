import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useHealth } from '../../hooks/useHealth'
import { apiClient } from '../../services/api'

vi.mock('../../services/api', () => ({
  apiClient: {
    getHealth: vi.fn(),
  },
}))

const mockGetHealth = vi.mocked(apiClient.getHealth)

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useHealth', () => {
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

  it('polls health endpoint with expected query options', async () => {
    mockGetHealth.mockResolvedValue({ data: { status: 'ok' } })

    const { result } = renderHook(() => useHealth(), {
      wrapper: createWrapper(queryClient),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetHealth).toHaveBeenCalledTimes(1)

    const query = queryClient.getQueryCache().find(['health'])
    expect(query?.options.refetchInterval).toBe(60_000)
    expect(query?.options.retry).toBe(true)
    expect(query?.options.staleTime).toBe(0)
  })
})
