/**
 * TanStack Query configuration
 * Configures cache-aware API consumption with stale-while-revalidate
 */

import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: 30 seconds (matches backend cache strategy)
      staleTime: 30 * 1000,
      // Cache time: 5 minutes
      gcTime: 5 * 60 * 1000,
      // Retry on failure with exponential backoff
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors (client errors)
        if (error instanceof Error && 'statusCode' in error) {
          const statusCode = (error as { statusCode: number }).statusCode
          if (statusCode >= 400 && statusCode < 500) {
            return false
          }
        }
        // Retry up to 3 times for other errors
        return failureCount < 3
      },
      retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus for real-time updates
      refetchOnWindowFocus: true,
      // Don't refetch on mount if data is fresh
      refetchOnMount: false,
    },
    mutations: {
      retry: false,
    },
  },
})
