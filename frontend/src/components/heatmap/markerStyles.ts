/**
 * BVV-Style Marker Utilities
 * Color constants and utilities for styled map markers
 */

import type { ExpressionSpecification } from '@maplibre/maplibre-gl-style-spec'

/**
 * BVV transit colors for map markers
 * These are the official BVV/NVBO colors used in transit maps
 */
export const BVV_COLORS = {
  // Transport mode colors
  ubahn: '#0065AE', // U-Bahn blue
  sbahn: '#00AB4E', // S-Bahn green
  tram: '#D60F26', // Tram red
  bus: '#00558C', // Bus dark blue
  regional: '#6b7280', // Regional gray

  // Status/intensity colors (gradient from healthy to critical)
  healthy: '#00AB4E', // S-Bahn green
  warning: '#F59E0B', // Amber/orange
  critical: '#D60F26', // Tram red

  // Marker stroke colors
  strokeDark: 'rgba(255, 255, 255, 0.75)',
  strokeLight: 'rgba(255, 255, 255, 0.90)',
} as const

/**
 * Get marker color based on intensity (0-1) using BVV status gradient
 * @param intensity - Normalized intensity value (0 = healthy, 1 = critical)
 * @returns RGBA color string
 */
export function getBVVMarkerColor(intensity: number): string {
  // BVV gradient: green → amber → red
  if (intensity >= 0.8) return 'rgba(214, 15, 38, 1.0)' // critical - Tram red
  if (intensity >= 0.6) return 'rgba(214, 15, 38, 0.92)' // high critical
  if (intensity >= 0.4) return 'rgba(245, 158, 11, 0.90)' // warning - Amber
  if (intensity >= 0.2) return 'rgba(245, 158, 11, 0.75)' // low warning
  return 'rgba(0, 171, 78, 0.75)' // healthy - S-Bahn green
}

/**
 * Get marker glow color (more transparent version of fill color)
 */
export function getBVVGlowColor(intensity: number): string {
  if (intensity >= 0.8) return 'rgba(214, 15, 38, 0.32)'
  if (intensity >= 0.6) return 'rgba(214, 15, 38, 0.28)'
  if (intensity >= 0.4) return 'rgba(245, 158, 11, 0.28)'
  if (intensity >= 0.2) return 'rgba(245, 158, 11, 0.20)'
  return 'rgba(0, 171, 78, 0.20)'
}

/**
 * MapLibre color expression for point colors based on intensity
 * Uses BVV gradient: green (healthy) → amber (warning) → red (critical)
 */
export const BVV_POINT_COLOR: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'intensity'], 0],
  0,
  'rgba(0, 171, 78, 0.75)', // healthy - S-Bahn green
  0.2,
  'rgba(245, 158, 11, 0.75)', // low warning - amber
  0.4,
  'rgba(245, 158, 11, 0.90)', // warning - amber
  0.6,
  'rgba(214, 15, 38, 0.92)', // high critical - tram red
  1,
  'rgba(214, 15, 38, 1.0)', // critical - tram red
]

/**
 * MapLibre color expression for cluster colors based on average intensity
 */
export const BVV_CLUSTER_COLOR: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  [
    '/',
    ['coalesce', ['get', 'intensity_sum'], 0],
    ['max', 1, ['coalesce', ['get', 'point_count'], 1]],
  ],
  0,
  'rgba(0, 171, 78, 0.65)', // healthy
  0.3,
  'rgba(245, 158, 11, 0.75)', // warning
  0.6,
  'rgba(214, 15, 38, 0.82)', // critical
  1,
  'rgba(214, 15, 38, 1.0)', // severe
]

/**
 * MapLibre color expression for cluster glow
 */
export const BVV_CLUSTER_GLOW: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  [
    '/',
    ['coalesce', ['get', 'intensity_sum'], 0],
    ['max', 1, ['coalesce', ['get', 'point_count'], 1]],
  ],
  0,
  'rgba(0, 171, 78, 0.20)', // healthy glow
  0.3,
  'rgba(245, 158, 11, 0.28)', // warning glow
  0.6,
  'rgba(214, 15, 38, 0.32)', // critical glow
  1,
  'rgba(214, 15, 38, 0.38)', // severe glow
]

/**
 * Marker radius expression for zoom-based sizing
 */
export const BVV_MARKER_RADIUS: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  0,
  4,
  8,
  7,
  12,
  9,
  15,
  11,
]

/**
 * Cluster radius expression
 */
export const BVV_CLUSTER_RADIUS: ExpressionSpecification = [
  'step',
  ['get', 'point_count'],
  18,
  10,
  22,
  50,
  26,
]

/**
 * Glow radius expression (larger than marker)
 */
export const BVV_GLOW_RADIUS: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  0,
  8,
  8,
  14,
  12,
  18,
  15,
  22,
]

/**
 * Cluster glow radius
 */
export const BVV_CLUSTER_GLOW_RADIUS: ExpressionSpecification = [
  'step',
  ['get', 'point_count'],
  24,
  10,
  30,
  50,
  36,
]
