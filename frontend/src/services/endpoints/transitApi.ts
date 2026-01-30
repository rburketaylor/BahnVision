/**
 * Transit API endpoints
 * Endpoint-specific methods for GTFS-based Germany-wide transit data
 */

import type { HealthResponse } from '../../types/api'
import type {
  HeatmapOverviewParams,
  HeatmapOverviewResponse,
  HeatmapParams,
  HeatmapResponse,
} from '../../types/heatmap'
import type {
  TransitDeparturesParams,
  TransitDeparturesResponse,
  TransitNearbyStopsParams,
  TransitStop,
  TransitStopSearchParams,
  TransitStopSearchResponse,
  StationStats,
  StationStatsParams,
  StationTrends,
  StationTrendsParams,
} from '../../types/gtfs'
import type { IngestionStatus } from '../../types/ingestion'
import { ApiError, type ApiResponse } from '../apiTypes'
import { httpClient } from '../httpClient'

/**
 * Build a query string from params object
 * Handles arrays by repeating the key and skips nullish values
 */
function buildQueryString(params: Partial<Record<string, unknown>>): string {
  const searchParams = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return

    if (Array.isArray(value)) {
      value.forEach(item => searchParams.append(key, String(item)))
    } else {
      searchParams.append(key, String(value))
    }
  })

  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

/**
 * Transit API client for GTFS-based endpoints
 */
class TransitApiClient {
  /**
   * Health check endpoint
   */
  async getHealth(): Promise<ApiResponse<HealthResponse>> {
    return httpClient.request<HealthResponse>('/api/v1/health')
  }

  /**
   * Search for stops by name
   */
  async searchStops(
    params: TransitStopSearchParams
  ): Promise<ApiResponse<TransitStopSearchResponse>> {
    const queryString = buildQueryString(params as unknown as Record<string, unknown>)
    return httpClient.request<TransitStopSearchResponse>(
      `/api/v1/transit/stops/search${queryString}`,
      {
        timeout: 8000,
      }
    )
  }

  /**
   * Get details for a specific stop
   */
  async getStop(stopId: string): Promise<ApiResponse<TransitStop>> {
    return httpClient.request<TransitStop>(`/api/v1/transit/stops/${encodeURIComponent(stopId)}`, {
      timeout: 5000,
    })
  }

  /**
   * Find stops near a location
   */
  async getNearbyStops(params: TransitNearbyStopsParams): Promise<ApiResponse<TransitStop[]>> {
    const queryString = buildQueryString(params as unknown as Record<string, unknown>)
    return httpClient.request<TransitStop[]>(`/api/v1/transit/stops/nearby${queryString}`, {
      timeout: 8000,
    })
  }

  /**
   * Get departures for a stop with real-time updates
   */
  async getDepartures(
    params: TransitDeparturesParams
  ): Promise<ApiResponse<TransitDeparturesResponse>> {
    const queryString = buildQueryString(params as unknown as Record<string, unknown>)
    return httpClient.request<TransitDeparturesResponse>(
      `/api/v1/transit/departures${queryString}`,
      {
        timeout: 10000,
      }
    )
  }

  /**
   * Get station statistics (cancellation/delay rates)
   */
  async getStationStats(params: StationStatsParams): Promise<ApiResponse<StationStats>> {
    const { stop_id, ...queryParams } = params
    const queryString = buildQueryString(queryParams as Record<string, unknown>)
    return httpClient.request<StationStats>(
      `/api/v1/transit/stops/${encodeURIComponent(stop_id)}/stats${queryString}`,
      {
        timeout: 10000,
      }
    )
  }

  /**
   * Get station trends (historical performance data)
   */
  async getStationTrends(params: StationTrendsParams): Promise<ApiResponse<StationTrends>> {
    const { stop_id, ...queryParams } = params
    const queryString = buildQueryString(queryParams as Record<string, unknown>)
    return httpClient.request<StationTrends>(
      `/api/v1/transit/stops/${encodeURIComponent(stop_id)}/trends${queryString}`,
      {
        timeout: 10000,
      }
    )
  }

  /**
   * Heatmap cancellations endpoint
   */
  async getHeatmapData(params: HeatmapParams = {}): Promise<ApiResponse<HeatmapResponse>> {
    const apiParams: Record<string, unknown> = {
      time_range: params.time_range,
      bucket_width: params.bucket_width,
      zoom: params.zoom,
      max_points: params.max_points,
    }

    if (params.transport_modes && params.transport_modes.length > 0) {
      apiParams.transport_modes = params.transport_modes.join(',')
    }

    const queryString = buildQueryString(apiParams)
    // Use longer timeout for large time ranges (7d, 30d)
    const timeout = params.time_range === '7d' || params.time_range === '30d' ? 30000 : 15000
    return httpClient.request<HeatmapResponse>(`/api/v1/heatmap/cancellations${queryString}`, {
      timeout,
    })
  }

  /**
   * Get lightweight heatmap overview (all impacted stations)
   */
  async getHeatmapOverview(
    params: HeatmapOverviewParams = {}
  ): Promise<ApiResponse<HeatmapOverviewResponse>> {
    const apiParams: Record<string, unknown> = {
      time_range: params.time_range,
      bucket_width: params.bucket_width,
      metrics: params.metrics,
    }

    if (params.transport_modes && params.transport_modes.length > 0) {
      apiParams.transport_modes = params.transport_modes.join(',')
    }

    const queryString = buildQueryString(apiParams)
    // Use longer timeout for large time ranges (7d, 30d) that query daily summaries
    const timeout = params.time_range === '7d' || params.time_range === '30d' ? 30000 : 20000
    return httpClient.request<HeatmapOverviewResponse>(`/api/v1/heatmap/overview${queryString}`, {
      timeout,
    })
  }

  /**
   * Metrics endpoint (returns plain text)
   */
  async getMetrics(): Promise<string> {
    const url = `${httpClient.baseUrl}/metrics`
    const response = await fetch(url)

    if (!response.ok) {
      throw new ApiError(`Failed to fetch metrics: ${response.statusText}`, response.status)
    }

    return response.text()
  }

  /**
   * Get ingestion status (GTFS feed and RT harvester)
   */
  async getIngestionStatus(): Promise<ApiResponse<IngestionStatus>> {
    return httpClient.request<IngestionStatus>('/api/v1/system/ingestion-status', {
      timeout: 5000,
    })
  }
}

// Export singleton instance
export const transitApiClient = new TransitApiClient()
