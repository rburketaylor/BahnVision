/**
 * API type definitions based on backend REST interface
 * Reference: frontend/api-integration.md
 */

export type TransportType =
  | 'BAHN'
  | 'SBAHN'
  | 'UBAHN'
  | 'TRAM'
  | 'BUS'
  | 'REGIONAL_BUS'
  | 'SCHIFF'
  | 'SEV'
// SEV included for type compatibility but not shown in UI due to API issues

export type CacheStatus = 'hit' | 'miss' | 'stale' | 'stale-refresh'

// Health endpoint types
export interface HealthResponse {
  status: 'ok'
  version?: string
  uptime_seconds?: number
}

// Station search types
export interface Station {
  id: string
  name: string
  place: string
  latitude: number
  longitude: number
}

export interface StationSearchResponse {
  query: string
  results: Station[]
}

// Departures types
export interface Departure {
  planned_time: string | null
  realtime_time: string | null
  delay_minutes: number
  platform: string | null
  realtime: boolean
  line: string
  destination: string
  transport_type: TransportType
  icon: string | null
  cancelled: boolean
  messages: string[]
}

export interface DeparturesResponse {
  station: Station
  departures: Departure[]
}

// Error response type
export interface ErrorResponse {
  detail: string
}

// Query parameters types
export interface StationSearchParams {
  query: string
  limit?: number
}

export interface DeparturesParams {
  station: string
  limit?: number
  offset?: number
  from?: string // UTC ISO timestamp
  window_minutes?: number
  transport_type?: TransportType[]
}
