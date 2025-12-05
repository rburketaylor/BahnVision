/**
 * API client for BahnVision backend
 * 
 * This file exports the Transit API client which provides GTFS-based
 * Germany-wide transit data. The transit API replaces the previous MVG-only
 * implementation with broader coverage and real-time GTFS-RT updates.
 */

// Re-export types
export { ApiError, type ApiResponse } from './apiTypes'

// Re-export transit API client as the main client
export { transitApiClient as apiClient } from './endpoints/transitApi'

// Also export the named transit client for explicit usage
export { transitApiClient } from './endpoints/transitApi'
