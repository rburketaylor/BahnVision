/**
 * Health check hook
 * Polls backend health status every 60 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.getHealth(),
    // Poll every 60 seconds
    refetchInterval: 60 * 1000,
    // Keep retrying on failure
    retry: true,
    // Always consider data stale to enable polling
    staleTime: 0,
  })
}
