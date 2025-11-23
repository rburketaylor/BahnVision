/**
 * API client for BahnVision backend
 * Backward compatibility barrel export
 *
 * This file re-exports the new modular API client structure while maintaining
 * backward compatibility with existing code that imports from '../services/api'
 */

// Re-export types
export { ApiError, type ApiResponse } from './apiTypes'

// Re-export API client as singleton
export { mvgApiClient as apiClient } from './endpoints/mvgApi'
