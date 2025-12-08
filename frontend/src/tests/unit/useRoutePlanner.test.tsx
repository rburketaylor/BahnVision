import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRoutePlanner } from '../../hooks/useRoutePlanner'
import type { RoutePlanParams } from '../../types/api'

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
  })

  it('returns an error since route planning is not yet implemented', async () => {
    const params: RoutePlanParams = {
      origin: 'de:1',
      destination: 'de:2',
    }

    const { result } = renderHook(() => useRoutePlanner({ params }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
    })

    expect(result.current.error?.message).toContain('not yet available')
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
    expect(result.current.error).toBeNull()
  })
})
