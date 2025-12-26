/**
 * Tests for query-client configuration
 * Target: lib/query-client.ts (0% mutation score → 60%+)
 */

import { describe, it, expect } from 'vitest'
import { queryClient } from '../../lib/query-client'

describe('queryClient configuration', () => {
  describe('default query options', () => {
    it('has staleTime of 30 seconds', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(defaultOptions.queries?.staleTime).toBe(30 * 1000)
    })

    it('has gcTime (cache time) of 5 minutes', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(defaultOptions.queries?.gcTime).toBe(5 * 60 * 1000)
    })

    it('enables refetchOnWindowFocus', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(defaultOptions.queries?.refetchOnWindowFocus).toBe(true)
    })

    it('disables refetchOnMount for fresh data', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(defaultOptions.queries?.refetchOnMount).toBe(false)
    })
  })

  describe('retry logic', () => {
    it('has a retry function defined', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(typeof defaultOptions.queries?.retry).toBe('function')
    })

    it('does not retry on 4xx client errors', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      const retryFn = defaultOptions.queries?.retry as (
        failureCount: number,
        error: Error
      ) => boolean

      // Create an error with statusCode 400
      const clientError = Object.assign(new Error('Bad Request'), { statusCode: 400 })
      expect(retryFn(1, clientError)).toBe(false)

      // Create an error with statusCode 404
      const notFoundError = Object.assign(new Error('Not Found'), { statusCode: 404 })
      expect(retryFn(1, notFoundError)).toBe(false)

      // Create an error with statusCode 422
      const validationError = Object.assign(new Error('Validation Error'), { statusCode: 422 })
      expect(retryFn(1, validationError)).toBe(false)

      // Create an error with statusCode 499
      const clientClosedError = Object.assign(new Error('Client Closed'), { statusCode: 499 })
      expect(retryFn(1, clientClosedError)).toBe(false)
    })

    it('retries up to 3 times for server errors', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      const retryFn = defaultOptions.queries?.retry as (
        failureCount: number,
        error: Error
      ) => boolean

      // Create a 500 server error
      const serverError = Object.assign(new Error('Server Error'), { statusCode: 500 })

      expect(retryFn(0, serverError)).toBe(true) // First retry
      expect(retryFn(1, serverError)).toBe(true) // Second retry
      expect(retryFn(2, serverError)).toBe(true) // Third retry
      expect(retryFn(3, serverError)).toBe(false) // Should not retry after 3
    })

    it('retries for network errors without statusCode', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      const retryFn = defaultOptions.queries?.retry as (
        failureCount: number,
        error: Error
      ) => boolean

      const networkError = new Error('Network Error')

      expect(retryFn(0, networkError)).toBe(true)
      expect(retryFn(1, networkError)).toBe(true)
      expect(retryFn(2, networkError)).toBe(true)
      expect(retryFn(3, networkError)).toBe(false)
    })
  })

  describe('retry delay', () => {
    it('has exponential backoff retry delay', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      const retryDelayFn = defaultOptions.queries?.retryDelay as (attemptIndex: number) => number

      // Check exponential backoff: 1000 * 2^attemptIndex, max 30000
      expect(retryDelayFn(0)).toBe(1000) // 1000 * 2^0 = 1000
      expect(retryDelayFn(1)).toBe(2000) // 1000 * 2^1 = 2000
      expect(retryDelayFn(2)).toBe(4000) // 1000 * 2^2 = 4000
      expect(retryDelayFn(3)).toBe(8000) // 1000 * 2^3 = 8000
      expect(retryDelayFn(4)).toBe(16000) // 1000 * 2^4 = 16000
      expect(retryDelayFn(5)).toBe(30000) // 1000 * 2^5 = 32000, capped at 30000
      expect(retryDelayFn(10)).toBe(30000) // Should never exceed 30000
    })
  })

  describe('mutation options', () => {
    it('disables retry for mutations', () => {
      const defaultOptions = queryClient.getDefaultOptions()
      expect(defaultOptions.mutations?.retry).toBe(false)
    })
  })
})
