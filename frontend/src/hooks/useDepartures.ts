/**
 * Departures hook
 * Fetches live departure data with auto-refresh every 30 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { DeparturesParams } from '../types/api'

export function useDepartures(params: DeparturesParams, enabled = true) {
  return useQuery({
    queryKey: ['departures', params],
    queryFn: () => apiClient.getDepartures(params),
    enabled,
    // Auto-refresh every 30 seconds
    refetchInterval: 30 * 1000,
    // Consider data stale after 30 seconds
    staleTime: 30 * 1000,
  })
}
