/**
 * Route planner hook
 * Plans routes between two stations with optional time constraints
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { RoutePlanParams } from '../types/api'

interface UseRoutePlannerParams {
  params?: RoutePlanParams
  enabled?: boolean
}

export function useRoutePlanner({ params, enabled = true }: UseRoutePlannerParams = {}) {
  const queryClient = useQueryClient()

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['route-plan', params],
    queryFn: () => {
      if (!params) {
        throw new Error('Route planning parameters are required')
      }
      return apiClient.planRoute(params)
    },
    enabled: enabled && !!params && !!params.origin && !!params.destination,
    staleTime: 1000 * 60 * 2, // 2 minutes
    retry: (failureCount, error) => {
      // Don't retry on validation errors (4xx)
      if (
        'statusCode' in error &&
        typeof error.statusCode === 'number' &&
        error.statusCode >= 400 &&
        error.statusCode < 500
      ) {
        return false
      }
      return failureCount < 2
    },
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

// Legacy export for backward compatibility
export function useRoutePlannerLegacy(params: RoutePlanParams, enabled = true) {
  return useQuery({
    queryKey: ['routes', 'plan', params],
    queryFn: () => apiClient.planRoute(params),
    enabled,
    // Cache route plans for 2 minutes
    staleTime: 2 * 60 * 1000,
  })
}
