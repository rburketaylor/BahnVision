/**
 * Heatmap hook
 * Fetches cancellation heatmap data with auto-refresh
 */

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { HeatmapParams } from '../types/heatmap'

interface UseHeatmapOptions {
  enabled?: boolean
  /** Enable auto-refresh every 5 minutes */
  autoRefresh?: boolean
}

export function useHeatmap(params: HeatmapParams = {}, options: UseHeatmapOptions = {}) {
  const { enabled = true, autoRefresh = true } = options

  return useQuery({
    queryKey: ['heatmap', 'cancellations', params],
    queryFn: () => apiClient.getHeatmapData(params),
    enabled,
    // Keep the previous response while refetching (e.g. after zoom changes)
    // to prevent the map from momentarily going blank.
    placeholderData: keepPreviousData,
    // Cache heatmap data for 5 minutes (matches backend cache TTL)
    staleTime: 5 * 60 * 1000,
    // Prevent duplicate requests
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    // Auto-refresh every 5 minutes when enabled
    ...(autoRefresh
      ? {
          refetchInterval: 5 * 60 * 1000,
        }
      : {
          refetchInterval: false,
        }),
  })
}
