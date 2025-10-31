/**
 * Route planner hook
 * Plans routes between two stations with optional time constraints
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { RoutePlanParams } from '../types/api'

export function useRoutePlanner(params: RoutePlanParams, enabled = true) {
  return useQuery({
    queryKey: ['routes', 'plan', params],
    queryFn: () => apiClient.planRoute(params),
    enabled,
    // Cache route plans for 2 minutes
    staleTime: 2 * 60 * 1000,
  })
}
