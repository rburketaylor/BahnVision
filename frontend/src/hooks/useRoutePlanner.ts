/**
 * Route planner hook
 * Plans routes between two stations with optional time constraints
 *
 * NOTE: Route planning is not yet available in the Transit API.
 * This hook is temporarily disabled and will throw an error if used.
 * TODO: Implement GTFS-based journey planning in Phase 5+
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { RoutePlanParams } from '../types/api'
import { ApiError } from '../services/apiTypes'

interface UseRoutePlannerParams {
  params?: RoutePlanParams
  enabled?: boolean
}

// Placeholder function that throws until route planning is implemented
async function planRoute(): Promise<never> {
  throw new ApiError(
    'Route planning is not yet available. This feature will be implemented in a future update.',
    501,
    'Route planning requires GTFS-based journey planning which is planned for Phase 5.'
  )
}

export function useRoutePlanner({ params, enabled = true }: UseRoutePlannerParams = {}) {
  const queryClient = useQueryClient()

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['route-plan', params],
    queryFn: () => {
      if (!params) {
        throw new Error('Route planning parameters are required')
      }
      return planRoute()
    },
    enabled: enabled && !!params && !!params.origin && !!params.destination,
    staleTime: 1000 * 60 * 2, // 2 minutes
    retry: false, // Don't retry since this always fails for now
  })

  // Invalidate query when parameters change significantly
  const invalidateRoutePlan = () => {
    queryClient.invalidateQueries({ queryKey: ['route-plan'] })
  }

  return {
    data,
    isLoading,
    isFetching,
    error,
    refetch,
    invalidateRoutePlan,
  }
}

// Legacy export for backward compatibility - also disabled
export function useRoutePlannerLegacy(params: RoutePlanParams, enabled = true) {
  return useQuery({
    queryKey: ['routes', 'plan', params],
    queryFn: () => planRoute(params),
    enabled,
    retry: false,
    staleTime: 2 * 60 * 1000,
  })
}
