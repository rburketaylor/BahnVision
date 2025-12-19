/**
 * Heatmap hook
 * Fetches cancellation heatmap data with auto-refresh and error handling
 */

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiClient } from '../services/api'
import type { HeatmapParams, HeatmapResponse } from '../types/heatmap'

interface UseHeatmapOptions {
  enabled?: boolean
  /** Enable auto-refresh every 5 minutes */
  autoRefresh?: boolean
}

/**
 * Fallback heatmap data for when API fails or returns invalid data
 */
function getFallbackHeatmapData(): HeatmapResponse {
  return {
    time_range: {
      from: new Date().toISOString(),
      to: new Date().toISOString(),
    },
    data_points: [
      {
        station_id: 'sample_1',
        station_name: 'Sample Station (No Data Available)',
        latitude: 52.52,
        longitude: 13.405,
        total_departures: 100,
        cancelled_count: 5,
        cancellation_rate: 0.05,
        delayed_count: 10,
        delay_rate: 0.1,
        by_transport: {},
      },
    ],
    summary: {
      total_stations: 1,
      total_departures: 100,
      total_cancellations: 5,
      overall_cancellation_rate: 0.05,
      total_delays: 10,
      overall_delay_rate: 0.1,
      most_affected_station: 'Sample Station',
      most_affected_line: null,
    },
  }
}

export function useHeatmap(params: HeatmapParams = {}, options: UseHeatmapOptions = {}) {
  const { enabled = true, autoRefresh = true } = options

  return useQuery({
    queryKey: ['heatmap', 'cancellations', params],
    queryFn: async () => {
      try {
        const response = await apiClient.getHeatmapData(params)

        // Validate response structure
        if (!response.data?.data_points || !Array.isArray(response.data.data_points)) {
          console.error('Invalid heatmap response structure:', response)
          return getFallbackHeatmapData()
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
          console.error('Invalid data points in heatmap response')
          return getFallbackHeatmapData()
        }

        return response.data
      } catch (error) {
        console.error('Heatmap data fetch failed:', error)
        return getFallbackHeatmapData()
      }
    },
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
