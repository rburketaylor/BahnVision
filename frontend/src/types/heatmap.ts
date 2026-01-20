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

/** Enabled metrics state - tracks which metrics are visible on the heatmap */
export interface HeatmapEnabledMetrics {
  cancellations: boolean
  delays: boolean
}

export const DEFAULT_ENABLED_METRICS: HeatmapEnabledMetrics = {
  cancellations: true,
  delays: true,
}

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
  last_updated_at?: string
}

/** Time range preset options */
export type TimeRangePreset = 'live' | '1h' | '6h' | '24h' | '7d' | '30d'

/** Lightweight heatmap point for overview display */
export interface HeatmapPointLight {
  /** GTFS stop_id identifier */
  id: string
  /** Station latitude (4 decimal precision) */
  lat: number
  /** Station longitude (4 decimal precision) */
  lon: number
  /** Intensity score 0-1 (normalized impact for heatmap weight) */
  i: number
  /** Station name (for hover tooltip) */
  n: string
}

/** Lightweight heatmap overview response */
export interface HeatmapOverviewResponse {
  time_range: HeatmapTimeRange
  points: HeatmapPointLight[]
  summary: HeatmapSummary
  last_updated_at?: string
  total_impacted_stations: number
}

/** Parameters for heatmap overview API requests */
export interface HeatmapOverviewParams {
  time_range?: TimeRangePreset
  transport_modes?: TransportType[]
  bucket_width?: number
}

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
  radius: 28,
  blur: 16,
  maxZoom: 17,
  max: 1.0,
  // Default to a warm "heat" palette. The map layer picks a theme-aware
  // config at runtime, but other consumers can safely use this as a baseline.
  gradient: {
    0.0: 'rgba(0, 0, 0, 0.0)',
    0.25: 'rgba(255, 168, 0, 0.35)',
    0.55: 'rgba(255, 98, 0, 0.65)',
    0.8: 'rgba(255, 20, 60, 0.85)',
    1.0: 'rgba(190, 0, 60, 1.0)',
  },
}

/** Theme-aware heatmap configuration (dark mode = warm glow) */
export const DARK_HEATMAP_CONFIG: HeatmapConfig = {
  radius: 32,
  blur: 18,
  maxZoom: 17,
  max: 1.0,
  gradient: {
    0.0: 'rgba(0, 0, 0, 0.0)',
    0.2: 'rgba(255, 168, 0, 0.30)',
    0.5: 'rgba(255, 98, 0, 0.62)',
    0.78: 'rgba(255, 20, 60, 0.82)',
    1.0: 'rgba(190, 0, 60, 1.0)',
  },
}

/** Theme-aware heatmap configuration (light mode = cool glow) */
export const LIGHT_HEATMAP_CONFIG: HeatmapConfig = {
  radius: 28,
  blur: 16,
  maxZoom: 17,
  max: 1.0,
  gradient: {
    0.0: 'rgba(0, 0, 0, 0.0)',
    0.2: 'rgba(34, 211, 238, 0.26)',
    0.5: 'rgba(59, 130, 246, 0.50)',
    0.78: 'rgba(99, 102, 241, 0.72)',
    1.0: 'rgba(139, 92, 246, 0.95)',
  },
}

/** Time range labels for display */
export const TIME_RANGE_LABELS: Record<TimeRangePreset, string> = {
  live: 'Live',
  '1h': 'Last hour',
  '6h': 'Last 6 hours',
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
}
