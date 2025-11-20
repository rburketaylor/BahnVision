/**
 * Shared API types
 * Contains error classes and response wrappers used across the API client
 */

import type { CacheStatus } from '../types/api'

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
