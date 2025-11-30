/**
 * MVG API endpoints
 * Endpoint-specific methods for interacting with the BahnVision backend
 */

import type {
  DeparturesParams,
  DeparturesResponse,
  HealthResponse,
  RoutePlanParams,
  RoutePlanResponse,
  StationSearchParams,
  StationSearchResponse,
} from '../../types/api'
import type { HeatmapParams, HeatmapResponse } from '../../types/heatmap'
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

class MvgApiClient {
  // Health endpoint
  async getHealth(): Promise<ApiResponse<HealthResponse>> {
    return httpClient.request<HealthResponse>('/api/v1/health')
  }

  // Station search endpoint
  async searchStations(params: StationSearchParams): Promise<ApiResponse<StationSearchResponse>> {
    const queryString = buildQueryString(params as unknown as Record<string, unknown>)
    // Use longer timeout for station search (8 seconds) - first searches can be slower
    return httpClient.request<StationSearchResponse>(`/api/v1/mvg/stations/search${queryString}`, {
      timeout: 8000,
    })
  }

  // Departures endpoint
  async getDepartures(params: DeparturesParams): Promise<ApiResponse<DeparturesResponse>> {
    const queryString = buildQueryString(params as unknown as Record<string, unknown>)

    // Scale timeout based on request complexity to handle backend processing time
    // and potential cache warmup scenarios for complex transport type combinations
    const transportCount = params.transport_type?.length || 0
    let timeout = 10000 // default timeout

    if (transportCount > 4) {
      // Very complex requests - use longer timeout (max 20s)
      timeout = 20000
    } else if (transportCount > 3) {
      // Complex requests - extended timeout (15s)
      timeout = 15000
    } else if (transportCount > 1) {
      // Multiple transport types - moderate timeout (12s)
      timeout = 12000
    }

    return httpClient.request<DeparturesResponse>(`/api/v1/mvg/departures${queryString}`, {
      timeout,
    })
  }

  // Route planning endpoint
  async planRoute(params: RoutePlanParams): Promise<ApiResponse<RoutePlanResponse>> {
    // Validate that only one time parameter is provided
    if (params.departure_time && params.arrival_time) {
      throw new ApiError(
        'Cannot specify both departure_time and arrival_time',
        422,
        'Provide either departure_time or arrival_time, not both'
      )
    }

    const queryString = buildQueryString(params as unknown as Record<string, unknown>)
    return httpClient.request<RoutePlanResponse>(`/api/v1/mvg/routes/plan${queryString}`)
  }

  // Heatmap cancellations endpoint
  async getHeatmapData(params: HeatmapParams = {}): Promise<ApiResponse<HeatmapResponse>> {
    // Convert transport_modes array to comma-separated string if provided
    const apiParams: Record<string, unknown> = {
      time_range: params.time_range,
      bucket_width: params.bucket_width,
    }

    if (params.transport_modes && params.transport_modes.length > 0) {
      apiParams.transport_modes = params.transport_modes.join(',')
    }

    const queryString = buildQueryString(apiParams)
    // Heatmap aggregation can take time, use extended timeout
    return httpClient.request<HeatmapResponse>(`/api/v1/heatmap/cancellations${queryString}`, {
      timeout: 15000,
    })
  }

  // Metrics endpoint (returns plain text)
  async getMetrics(): Promise<string> {
    const url = `${httpClient.baseUrl}/metrics`
    const response = await fetch(url)

    if (!response.ok) {
      throw new ApiError(`Failed to fetch metrics: ${response.statusText}`, response.status)
    }

    return response.text()
  }
}

// Export singleton instance
export const mvgApiClient = new MvgApiClient()
