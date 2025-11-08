/**
 * Station search hook
 * Provides autocomplete functionality with debouncing
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { StationSearchParams } from '../types/api'

export function useStationSearch(params: StationSearchParams, enabled = true) {
  return useQuery({
    queryKey: ['stations', 'search', params],
    queryFn: () => apiClient.searchStations(params),
    enabled: enabled && params.query.length > 0,
    // Cache search results for 5 minutes
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    // Optimized retry configuration for search
    retry: (failureCount, error) => {
      // Don't retry on timeout errors (408)
      if (error instanceof Error && 'statusCode' in error) {
        const statusCode = (error as { statusCode: number }).statusCode
        if (statusCode === 408 || statusCode === 429) {
          return false // Don't retry timeouts or rate limits
        }
        if (statusCode >= 400 && statusCode < 500) {
          return false // Don't retry client errors
        }
      }
      // Only retry once for search queries to avoid hanging
      return failureCount < 1
    },
    retryDelay: 1000, // Fixed 1 second delay for search
    // Disable refetch on window focus for search queries to avoid unexpected re-requests
    refetchOnWindowFocus: false,
  })
}
