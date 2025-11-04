/**
 * API type definitions based on backend REST interface
 * Reference: frontend/api-integration.md
 */

export type TransportType = 'BAHN' | 'SBAHN' | 'UBAHN' | 'TRAM' | 'BUS' | 'REGIONAL_BUS' | 'SEV' | 'SCHIFF'

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

// Routes types
export interface RouteStop {
  id: string | null
  name: string | null
  place: string | null
  latitude: number | null
  longitude: number | null
  planned_time: string | null
  realtime_time: string | null
  platform: string | null
  transport_type: TransportType | null
  line: string | null
  destination: string | null
  delay_minutes: number | null
  messages: string[]
}

export interface RouteLeg {
  origin: RouteStop | null
  destination: RouteStop | null
  transport_type: TransportType | null
  line: string | null
  direction: string | null
  duration_minutes: number | null
  distance_meters: number | null
  intermediate_stops: RouteStop[]
}

export interface RoutePlan {
  duration_minutes: number | null
  transfers: number | null
  departure: RouteStop | null
  arrival: RouteStop | null
  legs: RouteLeg[]
}

export interface RoutePlanResponse {
  origin: Station
  destination: Station
  plans: RoutePlan[]
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
  transport_type?: TransportType[]
}

export interface RoutePlanParams {
  origin: string
  destination: string
  departure_time?: string // ISO 8601
  arrival_time?: string // ISO 8601
  transport_type?: TransportType[]
}
