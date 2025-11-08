/**
 * API client for BahnVision backend
 * Thin fetch wrapper with automatic error handling and type safety
 */

import { config } from '../lib/config'
import type {
  CacheStatus,
  DeparturesParams,
  DeparturesResponse,
  ErrorResponse,
  HealthResponse,
  RoutePlanParams,
  RoutePlanResponse,
  StationSearchParams,
  StationSearchResponse,
} from '../types/api'

export class ApiError extends Error {
  statusCode: number
  detail?: string

  constructor(message: string, statusCode: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.detail = detail
  }
}

export interface ApiResponse<T> {
  data: T
  cacheStatus?: CacheStatus
  requestId?: string
}

class ApiClient {
  private baseUrl: string
  private readonly defaultTimeout = 10000 // 10 seconds default timeout

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit & { timeout?: number }
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`
    const timeout = options?.timeout ?? this.defaultTimeout

    if (config.enableDebugLogs) {
      console.log(`[API] ${options?.method || 'GET'} ${url} (timeout: ${timeout}ms)`)
    }

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      })

      clearTimeout(timeoutId)

      const cacheStatus = response.headers.get('X-Cache-Status') as CacheStatus | null
      const requestId = response.headers.get('X-Request-Id') || undefined

      if (!response.ok) {
        const errorData = (await response.json().catch(() => ({}))) as ErrorResponse
        throw new ApiError(
          `API request failed: ${response.statusText}`,
          response.status,
          errorData.detail
        )
      }

      const data = await response.json()

      if (config.enableDebugLogs) {
        console.log(`[API] Response:`, { cacheStatus, requestId, data })
      }

      return {
        data,
        cacheStatus: cacheStatus || undefined,
        requestId,
      }
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof ApiError) {
        throw error
      }

      // Handle abort errors (timeouts)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new ApiError(
          'Request timed out. Please check your connection and try again.',
          408,
          'Request timeout'
        )
      }

      throw new ApiError(
        `Network request failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0
      )
    }
  }

  private buildQueryString(params: Partial<Record<string, unknown>>): string {
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

  // Health endpoint
  async getHealth(): Promise<ApiResponse<HealthResponse>> {
    return this.request<HealthResponse>('/api/v1/health')
  }

  // Station search endpoint
  async searchStations(
    params: StationSearchParams
  ): Promise<ApiResponse<StationSearchResponse>> {
    const queryString = this.buildQueryString(params as unknown as Record<string, unknown>)
    // Use shorter timeout for search requests (5 seconds)
    return this.request<StationSearchResponse>(`/api/v1/mvg/stations/search${queryString}`, {
      timeout: 5000,
    })
  }

  // Departures endpoint
  async getDepartures(params: DeparturesParams): Promise<ApiResponse<DeparturesResponse>> {
    const queryString = this.buildQueryString(params as unknown as Record<string, unknown>)
    return this.request<DeparturesResponse>(`/api/v1/mvg/departures${queryString}`)
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

    const queryString = this.buildQueryString(params as unknown as Record<string, unknown>)
    return this.request<RoutePlanResponse>(`/api/v1/mvg/routes/plan${queryString}`)
  }

  // Metrics endpoint (returns plain text)
  async getMetrics(): Promise<string> {
    const url = `${this.baseUrl}/metrics`
    const response = await fetch(url)

    if (!response.ok) {
      throw new ApiError(`Failed to fetch metrics: ${response.statusText}`, response.status)
    }

    return response.text()
  }
}

// Export singleton instance
export const apiClient = new ApiClient(config.apiBaseUrl)
