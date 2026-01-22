/**
 * MapLibre Heatmap Component
 * Interactive MapLibre GL JS map with heatmap overlay for cancellation/delay data
 *
 * Features:
 * - Theme-aware basemap styles (no API key required)
 * - Native MapLibre heatmap layer (WebGL-based)
 * - GeoJSON clustering for station markers
 * - Smooth zoom and pan
 * - Support for both cancellation and delay metrics
 */

import { useEffect, useRef, useCallback, useMemo, useState, type ReactNode } from 'react'
import { StationPopup } from './StationPopup'
import DOMPurify from 'dompurify'
import maplibregl from 'maplibre-gl'
import React from 'react'
import { createRoot } from 'react-dom/client'
import type { ExpressionSpecification } from '@maplibre/maplibre-gl-style-spec'
import type {
  HeatmapDataPoint,
  HeatmapEnabledMetrics,
  HeatmapPointLight,
} from '../../types/heatmap'
import type { StationStats } from '../../types/gtfs'
import {
  DEFAULT_ZOOM,
  GERMANY_CENTER,
  DARK_HEATMAP_CONFIG,
  LIGHT_HEATMAP_CONFIG,
} from '../../types/heatmap'
import { useTheme } from '../../contexts/ThemeContext'
import {
  BVV_POINT_COLOR,
  BVV_CLUSTER_COLOR,
  BVV_CLUSTER_GLOW,
  BVV_MARKER_RADIUS,
  BVV_CLUSTER_RADIUS,
  BVV_GLOW_RADIUS,
  BVV_CLUSTER_GLOW_RADIUS,
  getBVVMarkerColor,
} from './markerStyles'

// Error Boundary for Heatmap component
interface HeatmapErrorBoundaryProps {
  children: ReactNode
  onReset: () => void
}

interface HeatmapErrorBoundaryState {
  hasError: boolean
}

class HeatmapErrorBoundary extends React.Component<
  HeatmapErrorBoundaryProps,
  HeatmapErrorBoundaryState
> {
  constructor(props: HeatmapErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): HeatmapErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(): void {
    // Error is already logged by React
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex items-center justify-center bg-destructive/10">
          <div className="text-center p-6 bg-card rounded-lg shadow-lg">
            <h3 className="text-lg font-semibold text-destructive mb-2">Heatmap Error</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Failed to load heatmap visualization
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false })
                this.props.onReset()
              }}
              className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90"
            >
              Retry
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

// Basemap styles (no API key required)
const LIGHT_MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const DARK_MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const MAP_VIEW_STORAGE_KEY = 'bahnvision-heatmap-view-v1'

type HeatmapResolvedTheme = 'light' | 'dark'

function getBasemapStyleForTheme(theme: HeatmapResolvedTheme): string {
  return theme === 'dark' ? DARK_MAP_STYLE : LIGHT_MAP_STYLE
}

function getHeatmapConfigForTheme(theme: HeatmapResolvedTheme) {
  return theme === 'dark' ? DARK_HEATMAP_CONFIG : LIGHT_HEATMAP_CONFIG
}

function gradientToHeatmapColorExpression(
  gradient: Record<number, string>
): ExpressionSpecification {
  const stops = Object.entries(gradient)
    .map(([k, v]) => [Number(k), v] as const)
    .filter(([k]) => !Number.isNaN(k))
    .sort((a, b) => a[0] - b[0])

  return [
    'interpolate',
    ['linear'],
    ['heatmap-density'],
    ...stops.flat(),
  ] as unknown as ExpressionSpecification
}

function loadSavedView(): { center: [number, number]; zoom: number } | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(MAP_VIEW_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || !('center' in parsed) || !('zoom' in parsed)) {
      return null
    }

    const center = (parsed as { center: unknown }).center
    const zoom = (parsed as { zoom: unknown }).zoom
    if (
      !Array.isArray(center) ||
      center.length !== 2 ||
      typeof center[0] !== 'number' ||
      typeof center[1] !== 'number' ||
      typeof zoom !== 'number' ||
      Number.isNaN(center[0]) ||
      Number.isNaN(center[1]) ||
      Number.isNaN(zoom)
    ) {
      return null
    }

    // Basic sanity constraints
    if (center[0] < -180 || center[0] > 180 || center[1] < -90 || center[1] > 90) return null
    if (zoom < 0 || zoom > 22) return null

    return { center: [center[0], center[1]], zoom }
  } catch {
    return null
  }
}

function saveView(center: maplibregl.LngLat, zoom: number) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      MAP_VIEW_STORAGE_KEY,
      JSON.stringify({ center: [center.lng, center.lat], zoom })
    )
  } catch {
    // Ignore storage failures (private mode / quota)
  }
}

interface MapLibreHeatmapProps {
  // Existing props (keep for backwards compatibility during migration)
  dataPoints?: HeatmapDataPoint[]

  // NEW: Lightweight points for overview mode
  overviewPoints?: HeatmapPointLight[]

  enabledMetrics: HeatmapEnabledMetrics
  isLoading?: boolean
  onStationSelect?: (stationId: string | null) => void
  onZoomChange?: (zoom: number) => void
  overlay?: ReactNode

  // NEW: Callback when station detail is needed
  onStationDetailRequested?: (stationId: string) => void

  // NEW: Station details props
  selectedStationId?: string | null
  stationStats?: StationStats | null
  isStationStatsLoading?: boolean
}

/**
 * Validate heatmap data points and filter out invalid entries
 */
function validateHeatmapData(dataPoints: HeatmapDataPoint[]): HeatmapDataPoint[] {
  if (!Array.isArray(dataPoints)) {
    console.error('Invalid dataPoints: not an array', dataPoints)
    return []
  }

  return dataPoints.filter((point, index) => {
    const isValid =
      typeof point?.latitude === 'number' &&
      typeof point?.longitude === 'number' &&
      !isNaN(point.latitude) &&
      !isNaN(point.longitude) &&
      typeof point?.total_departures === 'number' &&
      typeof point?.cancelled_count === 'number' &&
      typeof point?.delayed_count === 'number'

    if (!isValid) {
      console.warn('Invalid data point filtered at index', index, {
        latitude: point?.latitude,
        longitude: point?.longitude,
        total_departures: point?.total_departures,
      })
    }
    return isValid
  })
}

/**
 * Result of toGeoJSON - includes both active and coverage stations
 */
interface GeoJSONResult {
  active: GeoJSON.FeatureCollection
  coverage: GeoJSON.FeatureCollection
}

/**
 * Convert HeatmapDataPoint array to GeoJSON FeatureCollections
 * Separates "active" stations (with impact data) from "coverage" stations (healthy, 0 impact)
 * Note: GeoJSON uses [lng, lat] order, opposite of Leaflet's [lat, lng]
 */
function toGeoJSON(
  dataPoints: HeatmapDataPoint[],
  enabledMetrics: HeatmapEnabledMetrics
): GeoJSONResult {
  // Validate and filter data first
  const validPoints = validateHeatmapData(dataPoints)

  // Provide fallback for empty data
  if (validPoints.length === 0) {
    console.info('No valid heatmap data - returning empty feature collections')
    return {
      active: { type: 'FeatureCollection', features: [] },
      coverage: { type: 'FeatureCollection', features: [] },
    }
  }

  // Separate into active (with impact) and coverage (healthy/zero impact) stations
  const activeFeatures: GeoJSON.Feature[] = []
  const coverageFeatures: GeoJSON.Feature[] = []

  for (const point of validPoints) {
    const cancellationRate = point.cancellation_rate ?? 0
    const delayRate = point.delay_rate ?? 0
    const hasImpact = cancellationRate > 0 || delayRate > 0

    // Filter logic: respect metric toggles
    // Coverage stations (0 impact) are only included when BOTH metrics are enabled
    // This ensures "Show only Delays" doesn't show stations with 0 delays
    let includePoint = false
    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      // Both enabled: show all stations (impact OR coverage)
      includePoint = true
    } else if (enabledMetrics.delays) {
      // Delays only: show only if there are delays
      includePoint = delayRate > 0
    } else {
      // Cancellations only: show only if there are cancellations
      includePoint = cancellationRate > 0
    }

    if (!includePoint) continue

    // Calculate rate and intensity based on enabled metrics
    let rate: number
    let intensity: number

    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      // Combined: sum of both rates, saturate at 25%
      rate = cancellationRate + delayRate
      intensity = Math.min(rate * 4, 1) // saturate at 25%
    } else if (enabledMetrics.delays) {
      // Delays only: saturate at 20%
      rate = delayRate
      intensity = Math.min(rate * 5, 1)
    } else {
      // Cancellations only (or fallback): saturate at 10%
      rate = cancellationRate
      intensity = Math.min(rate * 10, 1)
    }

    const feature: GeoJSON.Feature = {
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [point.longitude, point.latitude], // [lng, lat] for GeoJSON
      },
      properties: {
        station_id: point.station_id ?? '',
        station_name: point.station_name ?? 'Unknown',
        cancellation_rate: cancellationRate,
        delay_rate: delayRate,
        rate: rate, // Active rate based on enabled metrics
        total_departures: point.total_departures ?? 0,
        cancelled_count: point.cancelled_count ?? 0,
        delayed_count: point.delayed_count ?? 0,
        intensity: intensity,
        is_coverage: !hasImpact, // Flag for coverage stations
      },
    }

    if (hasImpact) {
      activeFeatures.push(feature)
    } else {
      coverageFeatures.push(feature)
    }
  }

  return {
    active: {
      type: 'FeatureCollection',
      features: activeFeatures,
    },
    coverage: {
      type: 'FeatureCollection',
      features: coverageFeatures,
    },
  }
}

/**
 * Convert lightweight HeatmapPointLight array to GeoJSON
 */
function overviewToGeoJSON(points: HeatmapPointLight[]): GeoJSONResult {
  // In overview mode, all points are shown - filtering by metric happens at API level
  if (!points || points.length === 0) {
    return {
      active: { type: 'FeatureCollection', features: [] },
      coverage: { type: 'FeatureCollection', features: [] },
    }
  }

  const features: GeoJSON.Feature[] = points
    .filter(
      point =>
        typeof point.lat === 'number' &&
        typeof point.lon === 'number' &&
        !isNaN(point.lat) &&
        !isNaN(point.lon)
    )
    .map(point => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [point.lon, point.lat],
      },
      properties: {
        station_id: point.id,
        station_name: point.n,
        intensity: point.i,
        // These are approximations for backwards compat with existing styling
        rate: point.i * 0.25, // Intensity is 4x rate, so reverse
        is_coverage: point.i === 0,
      },
    }))

  // Separate into active vs coverage based on intensity
  const activeFeatures = features.filter(f => (f.properties?.intensity || 0) > 0)
  const coverageFeatures = features.filter(f => (f.properties?.intensity || 0) === 0)

  return {
    active: { type: 'FeatureCollection', features: activeFeatures },
    coverage: { type: 'FeatureCollection', features: coverageFeatures },
  }
}

/**
 * Get marker color based on normalized intensity (0..1).
 * Uses BVV gradient: green (healthy) → amber (warning) → red (critical).
 */
function getMarkerColor(intensity: number): string {
  return getBVVMarkerColor(intensity)
}

function sanitize(value: string): string {
  return DOMPurify.sanitize(value, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] })
}

/**
 * Suppress WebGL deprecation warnings in development
 */
function setupWebGLWarningSuppression() {
  // Only suppress warnings in development mode
  if (import.meta.env.MODE === 'development') {
    const originalConsoleWarn = console.warn
    console.warn = (...args) => {
      if (
        typeof args[0] === 'string' &&
        args[0].includes('texImage') &&
        args[0].includes('deprecated')
      ) {
        return // Skip WebGL deprecation warnings
      }
      originalConsoleWarn(...args)
    }
  }
}

export function MapLibreHeatmap({
  dataPoints,
  overviewPoints,
  enabledMetrics,
  isLoading = false,
  onStationSelect,
  onZoomChange,
  overlay,
  onStationDetailRequested,
  selectedStationId,
  stationStats,
  isStationStatsLoading,
}: MapLibreHeatmapProps) {
  // Setup WebGL warning suppression
  useEffect(() => {
    setupWebGLWarningSuppression()
  }, [])

  const { resolvedTheme } = useTheme()
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const popupContainerRef = useRef<HTMLDivElement | null>(null)
  const popupRootRef = useRef<ReturnType<typeof createRoot> | null>(null)
  const onStationSelectRef = useRef(onStationSelect)
  const enabledMetricsRef = useRef(enabledMetrics)
  const resolvedThemeRef = useRef<HeatmapResolvedTheme>(resolvedTheme)
  const styleUrlRef = useRef<string | null>(null)
  const geoJsonDataRef = useRef<GeoJSONResult | null>(null)
  const zoomDebounceTimerRef = useRef<number | null>(null)
  const saveViewTimerRef = useRef<number | null>(null)

  const [isStyleTransitioning, setIsStyleTransitioning] = useState(false)
  const [mapKey, setMapKey] = useState(Date.now())

  useEffect(() => {
    enabledMetricsRef.current = enabledMetrics
  }, [enabledMetrics])

  useEffect(() => {
    onStationSelectRef.current = onStationSelect
  }, [onStationSelect])

  useEffect(() => {
    resolvedThemeRef.current = resolvedTheme
  }, [resolvedTheme])

  // Memoize GeoJSON conversion to avoid recalculating on every render
  const geoJsonData = useMemo((): GeoJSONResult => {
    // Prefer overview points if provided (lightweight mode)
    if (overviewPoints && overviewPoints.length > 0) {
      return overviewToGeoJSON(overviewPoints)
    }
    // Fall back to full dataPoints (backwards compat)
    if (dataPoints && dataPoints.length > 0) {
      return toGeoJSON(dataPoints, enabledMetrics)
    }
    return {
      active: { type: 'FeatureCollection' as const, features: [] },
      coverage: { type: 'FeatureCollection' as const, features: [] },
    }
  }, [overviewPoints, dataPoints, enabledMetrics])

  useEffect(() => {
    geoJsonDataRef.current = geoJsonData
  }, [geoJsonData])

  // Update map data when dataPoints or enabledMetrics change
  const updateMapData = useCallback(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const activeSource = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
    if (activeSource) {
      activeSource.setData(geoJsonData.active)
    }

    const coverageSource = map.getSource('coverage-data') as maplibregl.GeoJSONSource | undefined
    if (coverageSource) {
      coverageSource.setData(geoJsonData.coverage)
    }
  }, [geoJsonData])

  const scheduleZoomCallback = useCallback(() => {
    const map = mapRef.current
    if (!map) return

    if (zoomDebounceTimerRef.current) {
      window.clearTimeout(zoomDebounceTimerRef.current)
    }

    zoomDebounceTimerRef.current = window.setTimeout(() => {
      onZoomChange?.(map.getZoom())
    }, 250)
  }, [onZoomChange])

  const scheduleViewSave = useCallback(() => {
    const map = mapRef.current
    if (!map) return

    if (saveViewTimerRef.current) {
      window.clearTimeout(saveViewTimerRef.current)
    }

    saveViewTimerRef.current = window.setTimeout(() => {
      saveView(map.getCenter(), map.getZoom())
    }, 500)
  }, [])

  // Initialize map - recreate when theme changes for reliable style switching
  useEffect(() => {
    if (!mapContainerRef.current) return

    // Clean up existing map before creating a new one (e.g., on theme change)
    if (mapRef.current) {
      if (zoomDebounceTimerRef.current) window.clearTimeout(zoomDebounceTimerRef.current)
      if (saveViewTimerRef.current) window.clearTimeout(saveViewTimerRef.current)
      popupRef.current?.remove()
      mapRef.current.remove()
      mapRef.current = null
    }

    const saved = loadSavedView()
    const initialCenter: [number, number] = saved?.center ?? [GERMANY_CENTER[1], GERMANY_CENTER[0]]
    const initialZoom = saved?.zoom ?? DEFAULT_ZOOM

    // Use the current theme from props, not from ref, since this effect should run on theme change
    const currentTheme: HeatmapResolvedTheme = resolvedTheme

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: getBasemapStyleForTheme(currentTheme),
      center: initialCenter, // [lng, lat] for MapLibre
      zoom: initialZoom,
    })

    mapRef.current = map
    styleUrlRef.current = getBasemapStyleForTheme(currentTheme)

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')

    // Helper function to ensure popup exists and has close handler set up
    const ensurePopup = () => {
      if (!popupRef.current) {
        popupRef.current = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          maxWidth: '300px',
        })

        const popup = popupRef.current as unknown as {
          on?: (event: string, cb: () => void) => void
        }
        if (typeof popup.on === 'function') {
          popup.on('close', () => {
            onStationSelectRef.current?.(null)
            // Clear the ref since popup is now closed
            popupRef.current = null
          })
        }
      }
      return popupRef.current
    }

    // Create popup instance for reuse
    ensurePopup()

    const ensureLayers = () => {
      const theme: HeatmapResolvedTheme = currentTheme
      const config = getHeatmapConfigForTheme(theme)
      const isDark = theme === 'dark'

      // Get the active data for the heatmap source
      const activeData = geoJsonDataRef.current?.active ?? geoJsonData.active

      if (!map.getSource('heatmap-data')) {
        map.addSource('heatmap-data', {
          type: 'geojson',
          data: activeData,
          generateId: true,
          cluster: true,
          clusterMaxZoom: 14,
          clusterRadius: 50,
          // Aggregate intensity so clusters can be styled by impact.
          clusterProperties: {
            intensity_sum: ['+', ['get', 'intensity']],
          },
        })
      }

      // Add coverage source for healthy (zero-impact) stations
      const coverageData = geoJsonDataRef.current?.coverage ?? geoJsonData.coverage
      if (!map.getSource('coverage-data')) {
        map.addSource('coverage-data', {
          type: 'geojson',
          data: coverageData,
          generateId: true,
        })
      }

      const heatmapColor = gradientToHeatmapColorExpression(config.gradient)

      // Heatmap layer (only for active/impacted stations)
      if (!map.getLayer('heatmap-layer')) {
        map.addLayer({
          id: 'heatmap-layer',
          type: 'heatmap',
          source: 'heatmap-data',
          maxzoom: config.maxZoom,
          paint: {
            'heatmap-weight': ['get', 'intensity'],
            'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
            'heatmap-color': heatmapColor,
            'heatmap-radius': [
              'interpolate',
              ['linear'],
              ['zoom'],
              0,
              Math.max(2, Math.round(config.radius * 0.15)),
              8,
              Math.max(6, Math.round(config.radius * 0.45)),
              15,
              config.radius,
            ],
            'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.9, 15, 0],
          },
        })
      }

      // Coverage stations layer - subtle skeleton visualization
      // Uses a neutral gray/blue color to show network coverage without implying issues
      if (!map.getLayer('coverage-skeleton-layer')) {
        map.addLayer({
          id: 'coverage-skeleton-layer',
          type: 'circle',
          source: 'coverage-data',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 8, 3, 12, 4],
            'circle-color': isDark ? 'rgba(148, 163, 184, 0.4)' : 'rgba(100, 116, 139, 0.35)',
            'circle-stroke-width': 1,
            'circle-stroke-color': isDark ? 'rgba(203, 213, 225, 0.5)' : 'rgba(71, 85, 105, 0.4)',
            'circle-opacity': 0.6,
          },
        })
      }

      // BVV cluster colors: green (healthy) → amber (warning) → red (critical)
      const clusterColor = BVV_CLUSTER_COLOR as unknown as ExpressionSpecification

      const clusterGlowColor = BVV_CLUSTER_GLOW as unknown as ExpressionSpecification

      // Cluster glow (beneath clusters) - BVV styling
      if (!map.getLayer('cluster-glow')) {
        map.addLayer({
          id: 'cluster-glow',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': clusterGlowColor,
            'circle-radius': BVV_CLUSTER_GLOW_RADIUS as unknown as ExpressionSpecification,
            'circle-blur': 0.9,
          },
        })
      }

      // Cluster circles - BVV styling
      if (!map.getLayer('clusters')) {
        map.addLayer({
          id: 'clusters',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': clusterColor,
            'circle-radius': BVV_CLUSTER_RADIUS as unknown as ExpressionSpecification,
            'circle-stroke-width': 2,
            'circle-stroke-color': isDark
              ? 'rgba(255, 248, 235, 0.65)'
              : 'rgba(255, 255, 255, 0.85)',
          },
        })
      }

      // Cluster count labels
      if (!map.getLayer('cluster-count')) {
        map.addLayer({
          id: 'cluster-count',
          type: 'symbol',
          source: 'heatmap-data',
          filter: ['has', 'point_count'],
          layout: {
            'text-field': '{point_count_abbreviated}',
            'text-font': ['Open Sans Bold'],
            'text-size': 12,
          },
          paint: {
            'text-color': 'rgba(10, 14, 20, 0.92)',
            'text-halo-color': 'rgba(255, 255, 255, 0.75)',
            'text-halo-width': 1,
          },
        })
      }

      // BVV point colors: green (healthy) → amber (warning) → red (critical)
      const pointColor = BVV_POINT_COLOR as unknown as ExpressionSpecification

      // Unclustered glow (beneath points) - BVV styling
      if (!map.getLayer('unclustered-glow')) {
        map.addLayer({
          id: 'unclustered-glow',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': pointColor,
            'circle-radius': BVV_GLOW_RADIUS as unknown as ExpressionSpecification,
            'circle-opacity': 0.28,
            'circle-blur': 0.9,
          },
        })
      }

      // Individual station markers (unclustered) - BVV styling
      if (!map.getLayer('unclustered-point')) {
        map.addLayer({
          id: 'unclustered-point',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': pointColor,
            'circle-radius': BVV_MARKER_RADIUS as unknown as ExpressionSpecification,
            'circle-stroke-width': 2,
            'circle-stroke-color': isDark
              ? 'rgba(255, 255, 255, 0.75)'
              : 'rgba(255, 255, 255, 0.90)',
          },
        })
      }

      // Keep sources in sync in case style was reloaded.
      const src = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
      const covSrc = map.getSource('coverage-data') as maplibregl.GeoJSONSource | undefined
      if (src && geoJsonDataRef.current) {
        src.setData(geoJsonDataRef.current.active)
      }
      if (covSrc && geoJsonDataRef.current) {
        covSrc.setData(geoJsonDataRef.current.coverage)
      }
    }

    // Setup layers when style loads (fires on initial load and after setStyle)
    map.on('style.load', () => {
      ensureLayers()
      setIsStyleTransitioning(false)
    })

    map.on('load', () => {
      ensureLayers()
      scheduleZoomCallback()
    })

    // Handle zoom changes (debounced to avoid thrashing API calls)
    map.on('zoomend', () => {
      scheduleZoomCallback()
      scheduleViewSave()
    })

    // Persist view position
    map.on('moveend', () => {
      scheduleViewSave()
    })

    // Click on cluster to zoom in
    map.on('click', 'clusters', async (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })
      if (!features.length) return

      const clusterFeature = features[0]
      const clusterId = Number(clusterFeature.properties?.cluster_id)
      const pointCount = Number(clusterFeature.properties?.point_count)
      if (!Number.isFinite(clusterId)) return

      const geometry = clusterFeature.geometry
      if (geometry.type !== 'Point') return

      const clusterCenter = geometry.coordinates as [number, number]
      const source = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
      if (!source) return

      // Known MapLibre issue: getClusterExpansionZoom can return unreliable values.
      // Instead, fit the bounds of cluster leaves (sampled) for a stable zoom.
      try {
        const leafLimit = Number.isFinite(pointCount)
          ? Math.min(Math.max(pointCount, 20), 200)
          : 200
        const leaves = await source.getClusterLeaves(clusterId, leafLimit, 0)

        const bounds = new maplibregl.LngLatBounds(clusterCenter, clusterCenter)
        for (const leaf of leaves) {
          if (leaf.geometry.type !== 'Point') continue
          const [lng, lat] = leaf.geometry.coordinates as [number, number]
          if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue
          bounds.extend([lng, lat])
        }

        // If bounds are effectively a single point, fall back to a controlled zoom bump.
        const sw = bounds.getSouthWest()
        const ne = bounds.getNorthEast()
        const isDegenerate = Math.abs(sw.lng - ne.lng) < 1e-6 && Math.abs(sw.lat - ne.lat) < 1e-6

        if (isDegenerate) {
          map.easeTo({
            center: clusterCenter,
            zoom: Math.min(map.getZoom() + 2, 16),
            duration: 650,
          })
          return
        }

        map.fitBounds(bounds, {
          padding: 96,
          duration: 700,
          maxZoom: 16,
        })
      } catch {
        // Safe fallback: still zoom in, but without relying on cluster expansion.
        map.easeTo({ center: clusterCenter, zoom: Math.min(map.getZoom() + 2, 16), duration: 650 })
      }
    })

    // Click on individual station marker
    map.on('click', 'unclustered-point', (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['unclustered-point'] })
      if (!features.length) return

      const props = features[0].properties
      if (!props) return

      const geometry = features[0].geometry
      if (geometry.type !== 'Point') return

      const coordinates = geometry.coordinates.slice() as [number, number]
      const stationId = sanitize(String(props.station_id ?? ''))
      const stationName = sanitize(String(props.station_name ?? 'Unknown'))

      // Check if this is an overview point (minimal data) or full data point
      const isOverviewPoint =
        !props.cancellation_rate && !props.delay_rate && props.intensity !== undefined

      if (isOverviewPoint && onStationDetailRequested) {
        // Close any existing popup first to avoid stale state
        popupRef.current?.remove()
        popupRef.current = null

        // Ensure we have a fresh popup instance
        ensurePopup()

        // Trigger on-demand detail fetch for overview points
        onStationDetailRequested(stationId)

        // Show loading popup while details load
        const loadingHtml = `
          <div class="bv-map-popup">
            <h4 class="bv-map-popup__title">${stationName}</h4>
            <div class="bv-map-popup__rows">
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__value">Loading details...</span>
              </div>
            </div>
          </div>
        `

        popupRef.current!.setLngLat(coordinates).setHTML(loadingHtml).addTo(map)
      } else {
        // Show full popup for regular data points
        const cancellationRate = props.cancellation_rate as number
        const delayRate = props.delay_rate as number
        const intensity = (props.intensity as number) ?? 0
        const color = getMarkerColor(intensity)

        // Show popup with both metrics - highlight based on what's enabled
        const em = enabledMetricsRef.current
        const bothEnabled = em.cancellations && em.delays
        const onlyDelays = !em.cancellations && em.delays
        const onlyCancellations = em.cancellations && !em.delays

        const popupContent = `
          <div class="bv-map-popup">
            <h4 class="bv-map-popup__title">${stationName}</h4>
            <div class="bv-map-popup__rows">
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label ${bothEnabled || onlyCancellations ? 'bv-map-popup__label--active' : ''}">Cancel Rate:</span>
                <span class="bv-map-popup__value" style="color: ${bothEnabled || onlyCancellations ? color : 'currentColor'}">
                  ${(cancellationRate * 100).toFixed(1)}%
                </span>
              </div>
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label ${bothEnabled || onlyDelays ? 'bv-map-popup__label--active' : ''}">Delay Rate:</span>
                <span class="bv-map-popup__value" style="color: ${bothEnabled || onlyDelays ? color : 'currentColor'}">
                  ${(delayRate * 100).toFixed(1)}%
                </span>
              </div>
              ${
                bothEnabled
                  ? `
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label bv-map-popup__label--active">Combined:</span>
                <span class="bv-map-popup__value" style="color: ${color}">
                  ${((cancellationRate + delayRate) * 100).toFixed(1)}%
                </span>
              </div>
              `
                  : ''
              }
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label">Departures:</span>
                <span class="bv-map-popup__value">${(props.total_departures as number).toLocaleString()}</span>
              </div>
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label">Cancelled:</span>
                <span class="bv-map-popup__value text-red-600">
                  ${(props.cancelled_count as number).toLocaleString()}
                </span>
              </div>
              <div class="bv-map-popup__row">
                <span class="bv-map-popup__label">Delayed:</span>
                <span class="bv-map-popup__value text-orange-600">
                  ${(props.delayed_count as number).toLocaleString()}
                </span>
              </div>
            </div>
            <a href="/station/${stationId}" class="bv-map-popup__link">
              Details →
            </a>
          </div>
        `

        // Ensure popup exists (it may have been closed and cleared)
        ensurePopup()
        popupRef.current!.setLngLat(coordinates).setHTML(popupContent).addTo(map)
      }

      // Notify parent of selection
      onStationSelectRef.current?.(stationId)
    })

    // Click on coverage station (healthy, zero-impact)
    map.on('click', 'coverage-skeleton-layer', (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['coverage-skeleton-layer'] })
      if (!features.length) return

      const props = features[0].properties
      if (!props) return

      const geometry = features[0].geometry
      if (geometry.type !== 'Point') return

      const coordinates = geometry.coordinates.slice() as [number, number]
      const cancellationRate = (props.cancellation_rate as number) ?? 0
      const delayRate = (props.delay_rate as number) ?? 0
      const stationName = sanitize(String(props.station_name ?? 'Unknown'))

      // Coverage stations use neutral styling in popup
      const neutralColor = '#64748b' // slate-500

      const stationId = sanitize(String(props.station_id ?? ''))
      const popupContent = `
        <div class="bv-map-popup">
          <h4 class="bv-map-popup__title">${stationName}</h4>
          <div class="bv-map-popup__rows">
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Status:</span>
              <span class="bv-map-popup__value" style="color: ${neutralColor}">
                Healthy (no issues)
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Cancel Rate:</span>
              <span class="bv-map-popup__value">
                ${(cancellationRate * 100).toFixed(1)}%
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Delay Rate:</span>
              <span class="bv-map-popup__value">
                ${(delayRate * 100).toFixed(1)}%
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Departures:</span>
              <span class="bv-map-popup__value">${((props.total_departures as number) ?? 0).toLocaleString()}</span>
            </div>
          </div>
          <a href="/station/${stationId}" class="bv-map-popup__link">
            Details →
          </a>
        </div>
      `

      // Ensure popup exists (it may have been closed and cleared)
      ensurePopup()
      popupRef.current!.setLngLat(coordinates).setHTML(popupContent).addTo(map)

      // Notify parent of selection
      onStationSelectRef.current?.(props.station_id as string)
    })

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      popupRef.current?.remove()
      popupRef.current = null
      onStationSelectRef.current?.(null)
    }
    window.addEventListener('keydown', handleKeyDown)

    // Change cursor on hover
    map.on('mouseenter', 'clusters', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'clusters', () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('mouseenter', 'unclustered-point', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'unclustered-point', () => {
      map.getCanvas().style.cursor = ''
    })
    // Hover on coverage stations
    map.on('mouseenter', 'coverage-skeleton-layer', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'coverage-skeleton-layer', () => {
      map.getCanvas().style.cursor = ''
    })

    mapRef.current = map

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      if (zoomDebounceTimerRef.current) window.clearTimeout(zoomDebounceTimerRef.current)
      if (saveViewTimerRef.current) window.clearTimeout(saveViewTimerRef.current)
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- geoJsonData accessed via ref; resolvedTheme triggers map recreation
  }, [resolvedTheme, scheduleViewSave, scheduleZoomCallback])

  const resetView = useCallback(() => {
    const map = mapRef.current
    if (!map) return

    popupRef.current?.remove()
    onStationSelectRef.current?.(null)

    try {
      window.localStorage.removeItem(MAP_VIEW_STORAGE_KEY)
    } catch {
      // Ignore storage failures
    }

    map.easeTo({
      center: [GERMANY_CENTER[1], GERMANY_CENTER[0]],
      zoom: DEFAULT_ZOOM,
      duration: 650,
    })
  }, [])

  // Update data when dataPoints or metric change
  useEffect(() => {
    updateMapData()
  }, [updateMapData])

  // Update popup when station stats data changes
  useEffect(() => {
    if (!selectedStationId || !popupRef.current || !mapRef.current) return

    const popup = popupRef.current

    // Find the station from overviewPoints to get basic info
    const station = overviewPoints?.find(p => p.id === selectedStationId)
    if (!station) return

    // Clean up previous React root
    if (popupRootRef.current) {
      popupRootRef.current.unmount()
      popupRootRef.current = null
    }

    // Create or reuse container
    if (!popupContainerRef.current) {
      popupContainerRef.current = document.createElement('div')
      popupContainerRef.current.className = 'bv-station-popup'
    }

    // Render StationPopup component into the container
    const root = createRoot(popupContainerRef.current)
    popupRootRef.current = root

    root.render(
      <StationPopup
        station={station}
        details={stationStats ?? undefined}
        isLoading={isStationStatsLoading ?? false}
      />
    )

    // Update popup with React-rendered content
    popup.setDOMContent(popupContainerRef.current).addTo(mapRef.current)

    return () => {
      // Cleanup on unmount or station change
      if (popupRootRef.current) {
        popupRootRef.current.unmount()
        popupRootRef.current = null
      }
    }
  }, [selectedStationId, stationStats, isStationStatsLoading, overviewPoints])

  // Cleanup React root when component unmounts
  useEffect(() => {
    return () => {
      if (popupRootRef.current) {
        popupRootRef.current.unmount()
      }
    }
  }, [])

  return (
    <HeatmapErrorBoundary
      onReset={() => {
        // Reset the map state
        if (mapRef.current) {
          mapRef.current.remove()
          mapRef.current = null
        }
        // Force re-render by toggling a key
        setMapKey(Date.now())
      }}
    >
      <div
        className="relative w-full h-full rounded-lg overflow-hidden border border-border"
        key={mapKey}
      >
        <div ref={mapContainerRef} className="absolute inset-0 z-0" />

        {/* Map UI helpers */}
        <div className="absolute right-4 top-16 z-[950] flex items-center gap-2">
          <button
            type="button"
            onClick={resetView}
            className="bg-card border border-border text-foreground px-3 py-2 rounded-lg text-xs font-medium shadow-sm hover:bg-muted transition-colors"
            aria-label="Reset map view"
            title="Reset map view"
          >
            Reset view
          </button>
        </div>

        {overlay}

        {/* Style-switch fade overlay */}
        <div
          className={`absolute inset-0 z-[900] pointer-events-none transition-opacity duration-300 ${
            isStyleTransitioning ? 'opacity-100' : 'opacity-0'
          } ${resolvedTheme === 'dark' ? 'bg-[#0b0f14]' : 'bg-white'}`}
        />

        {/* Loading overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-background/30 z-[1000] flex items-center justify-center pointer-events-none">
            <div className="text-center bg-card p-4 rounded-lg shadow-lg backdrop-blur-sm">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Loading heatmap data...</p>
            </div>
          </div>
        )}
      </div>
    </HeatmapErrorBoundary>
  )
}
