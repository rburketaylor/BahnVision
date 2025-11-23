/**
 * Core HTTP client
 * Generic fetch wrapper with timeout, error handling, and header parsing
 */

import { config } from '../lib/config'
import type { CacheStatus } from '../types/api'
import { ApiError, type ApiResponse } from './apiTypes'

export interface RequestOptions extends RequestInit {
  timeout?: number
}

class HttpClient {
  public baseUrl: string
  private readonly defaultTimeout = 10000 // 10 seconds default timeout

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  async request<T>(endpoint: string, options?: RequestOptions): Promise<ApiResponse<T>> {
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
        const errorData = (await response.json().catch(() => ({}))) as { detail?: string }
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
}

// Export singleton instance
export const httpClient = new HttpClient(config.apiBaseUrl)
