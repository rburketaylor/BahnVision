/**
 * useHeatmapOverview Hook
 * Fetches lightweight heatmap overview with all impacted stations
 */

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { HeatmapOverviewParams } from '../types/heatmap'

interface UseHeatmapOverviewOptions {
  enabled?: boolean
  /** Enable auto-refresh (live uses a faster cadence) */
  autoRefresh?: boolean
}

export function useHeatmapOverview(
  params: HeatmapOverviewParams = {},
  options: UseHeatmapOverviewOptions = {}
) {
  const { enabled = true, autoRefresh = true } = options
  const isLive = params.time_range === 'live'
  const refetchIntervalMs = isLive ? 60 * 1000 : 5 * 60 * 1000
  const staleTimeMs = isLive ? 30 * 1000 : 5 * 60 * 1000

  return useQuery({
    queryKey: ['heatmap', 'overview', params],
    queryFn: async () => {
      const response = await apiClient.getHeatmapOverview(params)

      // Validate response structure
      if (!response.data?.points || !Array.isArray(response.data.points)) {
        throw new Error('Invalid heatmap overview response structure')
      }

      // Validate each point has required fields
      const validData = response.data.points.every(
        point =>
          typeof point.lat === 'number' &&
          typeof point.lon === 'number' &&
          typeof point.i === 'number' &&
          !isNaN(point.lat) &&
          !isNaN(point.lon) &&
          !isNaN(point.i)
      )

      if (!validData) {
        throw new Error('Invalid points in heatmap overview response')
      }

      return response.data
    },
    enabled,
    placeholderData: keepPreviousData,
    staleTime: staleTimeMs,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    ...(autoRefresh ? { refetchInterval: refetchIntervalMs } : { refetchInterval: false }),
  })
}
