/**
 * Heatmap hook
 * Fetches cancellation heatmap data with auto-refresh and error handling
 */

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { HeatmapParams } from '../types/heatmap'

interface UseHeatmapOptions {
  enabled?: boolean
  /** Enable auto-refresh (live uses a faster cadence) */
  autoRefresh?: boolean
}

export function useHeatmap(params: HeatmapParams = {}, options: UseHeatmapOptions = {}) {
  const { enabled = true, autoRefresh = true } = options
  const isLive = params.time_range === 'live'
  const refetchIntervalMs = isLive ? 60 * 1000 : 5 * 60 * 1000
  const staleTimeMs = isLive ? 30 * 1000 : 5 * 60 * 1000

  return useQuery({
    queryKey: ['heatmap', 'cancellations', params],
    queryFn: async () => {
      const response = await apiClient.getHeatmapData(params)

      // Validate response structure - throw if invalid so error state is shown
      if (!response.data?.data_points || !Array.isArray(response.data.data_points)) {
        throw new Error('Invalid heatmap response structure')
      }

      // Validate each data point has required fields
      const validData = response.data.data_points.every(
        point =>
          typeof point.latitude === 'number' &&
          typeof point.longitude === 'number' &&
          !isNaN(point.latitude) &&
          !isNaN(point.longitude)
      )

      if (!validData) {
        throw new Error('Invalid data points in heatmap response')
      }

      return response.data
    },
    enabled,
    // Keep the previous response while refetching (e.g. after zoom changes)
    // to prevent the map from momentarily going blank.
    placeholderData: keepPreviousData,
    // Cache heatmap data; live uses a shorter stale time for freshness.
    staleTime: staleTimeMs,
    // Prevent duplicate requests
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    // Auto-refresh every 5 minutes when enabled
    ...(autoRefresh
      ? {
          refetchInterval: refetchIntervalMs,
        }
      : {
          refetchInterval: false,
        }),
  })
}
