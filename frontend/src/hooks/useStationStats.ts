/**
 * useStationStats Hook
 * React Query hook for fetching station statistics and trends
 */

import { useQuery } from '@tanstack/react-query'
import { transitApiClient } from '../services/endpoints/transitApi'
import type {
  StationStats,
  StationStatsTimeRange,
  StationTrends,
  TrendGranularity,
} from '../types/gtfs'

const STATION_STATS_STALE_TIME = 5 * 60 * 1000 // 5 minutes
const STATION_STATS_CACHE_TIME = 10 * 60 * 1000 // 10 minutes

interface UseStationStatsOptions {
  enabled?: boolean
  /** Whether to include network average rates (can be expensive for long time ranges). */
  includeNetworkAverages?: boolean
}

/**
 * Hook to fetch station statistics
 */
export function useStationStats(
  stopId: string | undefined,
  timeRange: StationStatsTimeRange = '24h',
  options: UseStationStatsOptions = {}
) {
  const { enabled = true, includeNetworkAverages = true } = options

  return useQuery<StationStats>({
    queryKey: ['stationStats', stopId, timeRange, includeNetworkAverages],
    queryFn: async () => {
      if (!stopId) throw new Error('Stop ID is required')
      const response = await transitApiClient.getStationStats({
        stop_id: stopId,
        time_range: timeRange,
        include_network_averages: includeNetworkAverages,
      })
      return response.data
    },
    enabled: enabled && !!stopId,
    staleTime: STATION_STATS_STALE_TIME,
    gcTime: STATION_STATS_CACHE_TIME,
    retry: 2,
  })
}

/**
 * Hook to fetch station trends
 */
export function useStationTrends(
  stopId: string | undefined,
  timeRange: StationStatsTimeRange = '24h',
  granularity: TrendGranularity = 'hourly',
  options: UseStationStatsOptions = {}
) {
  const { enabled = true } = options

  return useQuery<StationTrends>({
    queryKey: ['stationTrends', stopId, timeRange, granularity],
    queryFn: async () => {
      if (!stopId) throw new Error('Stop ID is required')
      const response = await transitApiClient.getStationTrends({
        stop_id: stopId,
        time_range: timeRange,
        granularity,
      })
      return response.data
    },
    enabled: enabled && !!stopId,
    staleTime: STATION_STATS_STALE_TIME,
    gcTime: STATION_STATS_CACHE_TIME,
    retry: 2,
  })
}
