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
  })
}
