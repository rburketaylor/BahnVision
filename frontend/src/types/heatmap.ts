/**
 * Heatmap types for cancellation data visualization
 * Mirrors backend models for type safety
 */

import type { TransportType } from './api'

/** Statistics for a single transport type */
export interface TransportStats {
  total: number
  cancelled: number
  delayed?: number
}

/** Heatmap metric types */
export type HeatmapMetric = 'cancellations' | 'delays'

export const HEATMAP_METRIC_LABELS: Record<HeatmapMetric, string> = {
  cancellations: 'Cancellations',
  delays: 'Delays',
}

/** A single data point representing cancellation data for a station */
export interface HeatmapDataPoint {
  station_id: string
  station_name: string
  latitude: number
  longitude: number
  total_departures: number
  cancelled_count: number
  cancellation_rate: number
  delayed_count?: number
  delay_rate?: number
  by_transport: Record<string, TransportStats>
}

/** Time range specification */
export interface HeatmapTimeRange {
  from: string
  to: string
}

/** Summary statistics for the heatmap */
export interface HeatmapSummary {
  total_stations: number
  total_departures: number
  total_cancellations: number
  overall_cancellation_rate: number
  total_delays?: number
  overall_delay_rate?: number
  most_affected_station: string | null
  most_affected_line: string | null
}

/** Response model for the heatmap cancellations endpoint */
export interface HeatmapResponse {
  time_range: HeatmapTimeRange
  data_points: HeatmapDataPoint[]
  summary: HeatmapSummary
}

/** Time range preset options */
export type TimeRangePreset = '1h' | '6h' | '24h' | '7d' | '30d'

/** Parameters for heatmap API requests */
export interface HeatmapParams {
  time_range?: TimeRangePreset
  transport_modes?: TransportType[]
  bucket_width?: number
  zoom?: number
  max_points?: number
}

/** Heatmap configuration for MapLibre heatmap layer */
export interface HeatmapConfig {
  radius: number
  blur: number
  maxZoom: number
  max: number
  gradient: Record<number, string>
}

/** Germany center coordinates [lat, lng] */
export const GERMANY_CENTER: [number, number] = [51.1, 10.4]

/** Default zoom level for Germany map */
export const DEFAULT_ZOOM = 6

/** Default heatmap configuration */
export const DEFAULT_HEATMAP_CONFIG: HeatmapConfig = {
  radius: 25,
  blur: 15,
  maxZoom: 17,
  max: 1.0,
  gradient: {
    0.0: 'rgba(0, 255, 0, 0.0)', // Green = no cancellations
    0.3: 'rgba(255, 255, 0, 0.6)', // Yellow = moderate
    0.7: 'rgba(255, 165, 0, 0.8)', // Orange = high
    1.0: 'rgba(255, 0, 0, 1.0)', // Red = severe
  },
}

/** Time range labels for display */
export const TIME_RANGE_LABELS: Record<TimeRangePreset, string> = {
  '1h': 'Last hour',
  '6h': 'Last 6 hours',
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
}
