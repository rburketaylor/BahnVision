/**
 * GTFS Transit API type definitions
 *
 * Types for the Germany-wide GTFS-based transit endpoints.
 * These mirror the backend Pydantic models in app/models/transit.py
 */

/**
 * GTFS route type values
 * See: https://gtfs.org/schedule/reference/#routestxt
 */
export const GtfsRouteType = {
  TRAM: 0,
  METRO: 1,
  RAIL: 2,
  BUS: 3,
  FERRY: 4,
  CABLE_CAR: 5,
  GONDOLA: 6,
  FUNICULAR: 7,
} as const

export type GtfsRouteType = (typeof GtfsRouteType)[keyof typeof GtfsRouteType]

/**
 * Schedule relationship status
 */
export type ScheduleRelationship = 'SCHEDULED' | 'SKIPPED' | 'NO_DATA' | 'UNSCHEDULED'

/**
 * A transit stop from GTFS data
 */
export interface TransitStop {
  /** GTFS stop_id */
  id: string
  /** Stop name */
  name: string
  /** Stop latitude */
  latitude: number
  /** Stop longitude */
  longitude: number
  /** Fare zone identifier */
  zone_id: string | null
  /** Wheelchair accessibility: 0=unknown, 1=accessible, 2=not accessible */
  wheelchair_boarding: number
}

/**
 * A transit route from GTFS data
 */
export interface TransitRoute {
  /** GTFS route_id */
  id: string
  /** Route short name (e.g., 'S1', 'U6') */
  short_name: string
  /** Route long name */
  long_name: string
  /** GTFS route_type */
  route_type: GtfsRouteType
  /** Route color as hex (e.g., 'FF0000') */
  color: string | null
  /** Route text color as hex */
  text_color: string | null
}

/**
 * A departure with combined schedule and real-time data
 */
export interface TransitDeparture {
  /** GTFS trip_id */
  trip_id: string
  /** GTFS route_id */
  route_id: string
  /** Route short name */
  route_short_name: string
  /** Route long name */
  route_long_name: string
  /** Trip destination/headsign */
  headsign: string
  /** GTFS stop_id */
  stop_id: string
  /** Stop name */
  stop_name: string
  /** Scheduled departure time (ISO 8601 UTC) */
  scheduled_departure: string
  /** Scheduled arrival time (ISO 8601 UTC) */
  scheduled_arrival: string | null
  /** Real-time predicted departure time (ISO 8601 UTC) */
  realtime_departure: string | null
  /** Real-time predicted arrival time (ISO 8601 UTC) */
  realtime_arrival: string | null
  /** Departure delay in seconds (positive=late) */
  departure_delay_seconds: number | null
  /** Arrival delay in seconds (positive=late) */
  arrival_delay_seconds: number | null
  /** Schedule status */
  schedule_relationship: ScheduleRelationship
  /** Vehicle identifier if available */
  vehicle_id: string | null
  /** Active service alerts */
  alerts: string[]
}

/**
 * Response for transit departures endpoint
 */
export interface TransitDeparturesResponse {
  /** Stop information */
  stop: TransitStop
  /** List of departures */
  departures: TransitDeparture[]
  /** Whether real-time data was available */
  realtime_available: boolean
}

/**
 * Response for transit stop search endpoint
 */
export interface TransitStopSearchResponse {
  /** Original search query */
  query: string
  /** Matching stops */
  results: TransitStop[]
}

/**
 * Response for transit route info endpoint
 */
export interface TransitRouteResponse {
  /** Route information */
  route: TransitRoute
  /** Active service alerts */
  alerts: string[]
}

/**
 * Query parameters for departures endpoint
 */
export interface TransitDeparturesParams {
  /** GTFS stop_id */
  stop_id: string
  /** Maximum number of departures (default: 10) */
  limit?: number
  /** Walking time offset in minutes */
  offset_minutes?: number
  /** Include real-time data (default: true) */
  include_realtime?: boolean
}

/**
 * Query parameters for stop search endpoint
 */
export interface TransitStopSearchParams {
  /** Search query */
  query: string
  /** Maximum number of results (default: 10) */
  limit?: number
}

/**
 * Query parameters for nearby stops endpoint
 */
export interface TransitNearbyStopsParams {
  /** Center latitude */
  latitude: number
  /** Center longitude */
  longitude: number
  /** Search radius in meters (default: 500) */
  radius_meters?: number
  /** Maximum number of results (default: 10) */
  limit?: number
}

/**
 * Helper function to get delay in minutes from seconds
 */
export function getDelayMinutes(delaySeconds: number | null): number {
  if (delaySeconds === null) return 0
  return Math.round(delaySeconds / 60)
}

/**
 * Helper function to determine if a departure is delayed
 */
export function isDelayed(departure: TransitDeparture, thresholdMinutes = 1): boolean {
  const delayMinutes = getDelayMinutes(departure.departure_delay_seconds)
  return delayMinutes >= thresholdMinutes
}

/**
 * Helper function to get the effective departure time
 * Returns real-time if available, otherwise scheduled
 */
export function getEffectiveDepartureTime(departure: TransitDeparture): string {
  return departure.realtime_departure ?? departure.scheduled_departure
}

/**
 * Map GTFS route type to display name
 */
export function getRouteTypeName(routeType: GtfsRouteType): string {
  const names: Record<GtfsRouteType, string> = {
    [GtfsRouteType.TRAM]: 'Tram',
    [GtfsRouteType.METRO]: 'U-Bahn',
    [GtfsRouteType.RAIL]: 'S-Bahn/Bahn',
    [GtfsRouteType.BUS]: 'Bus',
    [GtfsRouteType.FERRY]: 'Fähre',
    [GtfsRouteType.CABLE_CAR]: 'Seilbahn',
    [GtfsRouteType.GONDOLA]: 'Gondel',
    [GtfsRouteType.FUNICULAR]: 'Standseilbahn',
  }
  return names[routeType] ?? 'Unbekannt'
}

/**
 * Map route string prefix to GTFS route type
 */
export function getRouteTypeFromString(routeString: string): GtfsRouteType {
  const firstChar = routeString.charAt(0).toUpperCase()
  switch (firstChar) {
    case 'U':
      return GtfsRouteType.METRO
    case 'S':
      return GtfsRouteType.RAIL
    case 'T':
      return GtfsRouteType.TRAM
    case 'B':
    default:
      return GtfsRouteType.BUS
  }
}
