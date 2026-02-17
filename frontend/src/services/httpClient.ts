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

interface RequestContext {
  endpoint: string
  method: string
  timeout: number
  url: string
}

class HttpClient {
  public baseUrl: string
  private readonly defaultTimeout = 10000 // 10 seconds default timeout

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private buildRequestContext(endpoint: string, options?: RequestOptions): RequestContext {
    return {
      endpoint,
      method: (options?.method ?? 'GET').toUpperCase(),
      timeout: options?.timeout ?? this.defaultTimeout,
      url: `${this.baseUrl}${endpoint}`,
    }
  }

  private async parseErrorDetail(response: Response): Promise<string | undefined> {
    const contentType = response.headers.get('Content-Type')?.toLowerCase() ?? ''

    if (contentType.includes('application/json')) {
      const errorData = (await response.json().catch(() => ({}))) as { detail?: string }
      return errorData.detail
    }

    const text = await response.text().catch(() => '')
    const trimmedText = text.trim()
    if (!trimmedText) return undefined
    return trimmedText.slice(0, 500)
  }

  private buildDiagnostics(context: RequestContext, requestId?: string): string {
    const requestIdText = requestId ? `requestId=${requestId}` : 'requestId=unknown'
    return `${context.method} ${context.endpoint} (timeout=${context.timeout}ms, ${requestIdText})`
  }

  async requestText(endpoint: string, options?: RequestOptions): Promise<string> {
    const context = this.buildRequestContext(endpoint, options)

    if (config.enableDebugLogs) {
      console.log(`[API] ${context.method} ${context.url} (timeout: ${context.timeout}ms)`)
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), context.timeout)

    try {
      const response = await fetch(context.url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      })

      clearTimeout(timeoutId)

      const requestId = response.headers.get('X-Request-Id') || undefined

      if (!response.ok) {
        const detail = await this.parseErrorDetail(response)
        throw new ApiError(
          `API request failed: ${response.status} ${response.statusText}`,
          response.status,
          detail ?? this.buildDiagnostics(context, requestId)
        )
      }

      const data = await response.text()

      if (config.enableDebugLogs) {
        console.log(`[API] Text response:`, {
          contentLength: data.length,
          requestId,
        })
      }

      return data
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof ApiError) {
        throw error
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw new ApiError(
          'Request timed out. Please check your connection and try again.',
          408,
          this.buildDiagnostics(context)
        )
      }

      throw new ApiError(
        `Network request failed (${context.method} ${context.endpoint}): ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
        0,
        this.buildDiagnostics(context)
      )
    }
  }

  async request<T>(endpoint: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    const context = this.buildRequestContext(endpoint, options)

    if (config.enableDebugLogs) {
      console.log(`[API] ${context.method} ${context.url} (timeout: ${context.timeout}ms)`)
    }

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), context.timeout)

    try {
      const response = await fetch(context.url, {
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
        const detail = await this.parseErrorDetail(response)
        throw new ApiError(
          `API request failed: ${response.status} ${response.statusText}`,
          response.status,
          detail ?? this.buildDiagnostics(context, requestId)
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
          this.buildDiagnostics(context)
        )
      }

      throw new ApiError(
        `Network request failed (${context.method} ${context.endpoint}): ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
        0,
        this.buildDiagnostics(context)
      )
    }
  }
}

// Export singleton instance
export const httpClient = new HttpClient(config.apiBaseUrl)
