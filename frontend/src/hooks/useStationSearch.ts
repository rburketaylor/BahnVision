/**
 * Station search hook
 * Provides autocomplete functionality with debouncing
 * 
 * Uses the Transit API for GTFS-based stop search with Germany-wide coverage.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { TransitStopSearchParams } from '../types/gtfs'

export function useStationSearch(params: TransitStopSearchParams, enabled = true) {
  return useQuery({
    queryKey: ['stops', 'search', params],
    queryFn: () => apiClient.searchStops(params),
    enabled: enabled && params.query.length > 0,
    // Cache search results for 5 minutes
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    // Optimized retry configuration for search
    retry: (failureCount, error) => {
      // Don't retry on certain client errors
      if (error instanceof Error && 'statusCode' in error) {
        const statusCode = (error as { statusCode: number }).statusCode
        if (statusCode === 429) {
          return false // Don't retry rate limits
        }
        if (statusCode >= 400 && statusCode < 500 && statusCode !== 408) {
          return false // Don't retry client errors except timeouts
        }
      }
      // Allow 2 retries for search queries (total of 3 attempts) to handle temporary issues
      return failureCount < 2
    },
    retryDelay: attemptIndex => {
      // Progressive delay: 1s, 2s
      return Math.min(1000 * (attemptIndex + 1), 3000)
    },
    // Disable refetch on window focus for search queries to avoid unexpected re-requests
    refetchOnWindowFocus: false,
  })
}
