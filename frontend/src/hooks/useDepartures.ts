/**
 * Departures hook
 * Fetches departure data with configurable live/manual refresh modes
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { DeparturesParams } from '../types/api'

interface UseDeparturesOptions {
  enabled?: boolean
  live?: boolean // Enable auto-refresh for live mode
}

export function useDepartures(params: DeparturesParams, options: UseDeparturesOptions = {}) {
  const { enabled = true, live = false } = options

  return useQuery({
    queryKey: ['departures', params],
    queryFn: () => apiClient.getDepartures(params),
    enabled,
    // Prevent duplicate requests with the same key
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    // Auto-refresh configuration based on live mode
    ...(live
      ? {
          refetchInterval: 30 * 1000, // Auto-refresh every 30 seconds in live mode
          staleTime: 30 * 1000, // Consider data stale after 30 seconds
        }
      : {
          refetchInterval: false, // No auto-refresh in manual mode
          staleTime: 0, // Consider data immediately stale for manual refreshes
        }),
  })
}
