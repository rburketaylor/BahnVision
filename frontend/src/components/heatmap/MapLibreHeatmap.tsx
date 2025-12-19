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
import maplibregl from 'maplibre-gl'
import type { ExpressionSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { HeatmapDataPoint, HeatmapMetric } from '../../types/heatmap'
import {
  DEFAULT_ZOOM,
  GERMANY_CENTER,
  DARK_HEATMAP_CONFIG,
  LIGHT_HEATMAP_CONFIG,
} from '../../types/heatmap'
import { useTheme } from '../../contexts/ThemeContext'

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
  dataPoints: HeatmapDataPoint[]
  metric: HeatmapMetric
  isLoading?: boolean
  selectedStation?: string | null
  onStationSelect?: (stationId: string | null) => void
  onZoomChange?: (zoom: number) => void
  overlay?: ReactNode
}

/**
 * Convert HeatmapDataPoint array to GeoJSON FeatureCollection
 * Note: GeoJSON uses [lng, lat] order, opposite of Leaflet's [lat, lng]
 */
function toGeoJSON(
  dataPoints: HeatmapDataPoint[],
  metric: HeatmapMetric
): GeoJSON.FeatureCollection {
  // Filter out invalid points and ensure all numeric values are valid
  const validPoints = dataPoints.filter(
    point =>
      typeof point.latitude === 'number' &&
      typeof point.longitude === 'number' &&
      !isNaN(point.latitude) &&
      !isNaN(point.longitude)
  )

  return {
    type: 'FeatureCollection',
    features: validPoints.map(point => {
      const cancellationRate = point.cancellation_rate ?? 0
      const delayRate = point.delay_rate ?? 0
      const rate = metric === 'delays' ? delayRate : cancellationRate

      // Calculate intensity based on metric-specific scaling
      // Cancellations: saturate at 10% (rate * 10)
      // Delays: saturate at 20% (rate * 5)
      const intensity = metric === 'delays' ? Math.min(rate * 5, 1) : Math.min(rate * 10, 1)

      return {
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
          rate: rate, // Active rate based on selected metric
          total_departures: point.total_departures ?? 0,
          cancelled_count: point.cancelled_count ?? 0,
          delayed_count: point.delayed_count ?? 0,
          intensity: intensity,
        },
      }
    }),
  }
}

/**
 * Get marker color based on normalized intensity (0..1).
 */
function getMarkerColor(intensity: number): string {
  if (intensity > 0.8) return '#ef4444' // red
  if (intensity > 0.6) return '#f97316' // orange
  if (intensity > 0.4) return '#eab308' // yellow
  return '#22c55e' // green
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function MapLibreHeatmap({
  dataPoints,
  metric,
  isLoading = false,
  onStationSelect,
  onZoomChange,
  overlay,
}: MapLibreHeatmapProps) {
  const { resolvedTheme } = useTheme()
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const onStationSelectRef = useRef(onStationSelect)
  const metricRef = useRef(metric)
  const resolvedThemeRef = useRef<HeatmapResolvedTheme>(resolvedTheme)
  const styleUrlRef = useRef<string | null>(null)
  const geoJsonDataRef = useRef<GeoJSON.FeatureCollection | null>(null)
  const zoomDebounceTimerRef = useRef<number | null>(null)
  const saveViewTimerRef = useRef<number | null>(null)
  const hotspotMarkersRef = useRef<Map<number, maplibregl.Marker>>(new Map())
  const hotspotUpdateTimerRef = useRef<number | null>(null)
  const [isStyleTransitioning, setIsStyleTransitioning] = useState(false)

  useEffect(() => {
    metricRef.current = metric
  }, [metric])

  useEffect(() => {
    onStationSelectRef.current = onStationSelect
  }, [onStationSelect])

  useEffect(() => {
    resolvedThemeRef.current = resolvedTheme
  }, [resolvedTheme])

  // Memoize GeoJSON conversion to avoid recalculating on every render
  const geoJsonData = useMemo(() => toGeoJSON(dataPoints, metric), [dataPoints, metric])

  useEffect(() => {
    geoJsonDataRef.current = geoJsonData
  }, [geoJsonData])

  // Update map data when dataPoints or metric change
  const updateMapData = useCallback(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const source = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
    if (source) {
      source.setData(geoJsonData)
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

  const clearHotspotMarkers = useCallback(() => {
    hotspotMarkersRef.current.forEach(marker => marker.remove())
    hotspotMarkersRef.current.clear()
  }, [])

  const scheduleHotspotUpdate = useCallback(() => {
    const map = mapRef.current
    if (!map) return

    if (hotspotUpdateTimerRef.current) {
      window.clearTimeout(hotspotUpdateTimerRef.current)
    }

    hotspotUpdateTimerRef.current = window.setTimeout(() => {
      // Hotspot markers are a light DOM overlay for high-intensity clusters.
      // Keep them capped to preserve scroll/zoom performance.
      const theme = resolvedThemeRef.current
      const isDark = theme === 'dark'

      const clusterFeatures = map.queryRenderedFeatures({ layers: ['clusters'] })
      const scored = clusterFeatures
        .map(f => {
          const clusterId = Number(f.properties?.cluster_id)
          const pointCount = Number(f.properties?.point_count)
          const intensitySum = Number(f.properties?.intensity_sum)
          if (!Number.isFinite(clusterId) || !Number.isFinite(pointCount) || pointCount <= 0)
            return null
          const avgIntensity = Number.isFinite(intensitySum) ? intensitySum / pointCount : 0
          return {
            feature: f,
            clusterId,
            pointCount,
            avgIntensity,
            score: avgIntensity * Math.log10(pointCount + 1),
          }
        })
        .filter((x): x is NonNullable<typeof x> => x !== null)
        .filter(x => x.avgIntensity >= 0.75)
        .sort((a, b) => b.score - a.score)
        .slice(0, 25)

      const nextIds = new Set(scored.map(s => s.clusterId))
      // Remove stale markers
      hotspotMarkersRef.current.forEach((marker, id) => {
        if (!nextIds.has(id)) {
          marker.remove()
          hotspotMarkersRef.current.delete(id)
        }
      })

      for (const s of scored) {
        if (hotspotMarkersRef.current.has(s.clusterId)) continue
        if (s.feature.geometry.type !== 'Point') continue

        const el = document.createElement('div')
        el.className = `heatmap-hotspot ${isDark ? 'heatmap-hotspot--warm' : 'heatmap-hotspot--cool'}`
        const coords = s.feature.geometry.coordinates as [number, number]
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(coords)
          .addTo(map)
        hotspotMarkersRef.current.set(s.clusterId, marker)
      }
    }, 250)
  }, [])

  // Initialize map - recreate when theme changes for reliable style switching
  useEffect(() => {
    if (!mapContainerRef.current) return

    // Clean up existing map before creating a new one (e.g., on theme change)
    if (mapRef.current) {
      if (zoomDebounceTimerRef.current) window.clearTimeout(zoomDebounceTimerRef.current)
      if (saveViewTimerRef.current) window.clearTimeout(saveViewTimerRef.current)
      if (hotspotUpdateTimerRef.current) window.clearTimeout(hotspotUpdateTimerRef.current)
      clearHotspotMarkers()
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

    styleUrlRef.current = getBasemapStyleForTheme(currentTheme)

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')

    // Create popup instance for reuse
    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '300px',
    })

    const popup = popupRef.current as unknown as { on?: (event: string, cb: () => void) => void }
    if (typeof popup.on === 'function') {
      popup.on('close', () => {
        onStationSelectRef.current?.(null)
      })
    }

    const ensureLayers = () => {
      const theme: HeatmapResolvedTheme = currentTheme
      const config = getHeatmapConfigForTheme(theme)
      const isDark = theme === 'dark'

      if (!map.getSource('heatmap-data')) {
        map.addSource('heatmap-data', {
          type: 'geojson',
          data: geoJsonDataRef.current ?? geoJsonData,
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

      const heatmapColor = gradientToHeatmapColorExpression(config.gradient)

      // Heatmap layer
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

      const avgIntensityExpr = [
        '/',
        ['coalesce', ['get', 'intensity_sum'], 0],
        ['max', 1, ['coalesce', ['get', 'point_count'], 1]],
      ] as unknown as ExpressionSpecification

      const clusterColorWarm = [
        'interpolate',
        ['linear'],
        avgIntensityExpr,
        0,
        'rgba(255, 168, 0, 0.50)',
        0.5,
        'rgba(255, 98, 0, 0.75)',
        0.8,
        'rgba(255, 20, 60, 0.92)',
        1,
        'rgba(190, 0, 60, 1.0)',
      ] as unknown as ExpressionSpecification

      const clusterColorCool = [
        'interpolate',
        ['linear'],
        avgIntensityExpr,
        0,
        'rgba(34, 211, 238, 0.45)',
        0.5,
        'rgba(59, 130, 246, 0.70)',
        0.8,
        'rgba(99, 102, 241, 0.88)',
        1,
        'rgba(139, 92, 246, 1.0)',
      ] as unknown as ExpressionSpecification

      const clusterColor = (isDark ? clusterColorWarm : clusterColorCool) as ExpressionSpecification
      const clusterGlowColor = (isDark
        ? [
            'interpolate',
            ['linear'],
            avgIntensityExpr,
            0,
            'rgba(255, 168, 0, 0.18)',
            0.5,
            'rgba(255, 98, 0, 0.25)',
            0.8,
            'rgba(255, 20, 60, 0.30)',
            1,
            'rgba(190, 0, 60, 0.35)',
          ]
        : [
            'interpolate',
            ['linear'],
            avgIntensityExpr,
            0,
            'rgba(34, 211, 238, 0.15)',
            0.5,
            'rgba(59, 130, 246, 0.22)',
            0.8,
            'rgba(99, 102, 241, 0.28)',
            1,
            'rgba(139, 92, 246, 0.32)',
          ]) as unknown as ExpressionSpecification

      // Cluster glow (beneath clusters)
      if (!map.getLayer('cluster-glow')) {
        map.addLayer({
          id: 'cluster-glow',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': clusterGlowColor,
            'circle-radius': ['step', ['get', 'point_count'], 22, 10, 28, 50, 34],
            'circle-blur': 0.9,
          },
        })
      }

      // Cluster circles
      if (!map.getLayer('clusters')) {
        map.addLayer({
          id: 'clusters',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': clusterColor,
            'circle-radius': ['step', ['get', 'point_count'], 16, 10, 20, 50, 24],
            'circle-stroke-width': 1,
            'circle-stroke-color': isDark
              ? 'rgba(255, 248, 235, 0.55)'
              : 'rgba(255, 255, 255, 0.75)',
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

      const pointColorWarm = [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'intensity'], 0],
        0,
        'rgba(255, 168, 0, 0.65)',
        0.5,
        'rgba(255, 98, 0, 0.85)',
        0.8,
        'rgba(255, 20, 60, 0.95)',
        1,
        'rgba(190, 0, 60, 1.0)',
      ] as unknown as ExpressionSpecification
      const pointColorCool = [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'intensity'], 0],
        0,
        'rgba(34, 211, 238, 0.55)',
        0.5,
        'rgba(59, 130, 246, 0.78)',
        0.8,
        'rgba(99, 102, 241, 0.92)',
        1,
        'rgba(139, 92, 246, 1.0)',
      ] as unknown as ExpressionSpecification

      const pointColor = (isDark ? pointColorWarm : pointColorCool) as ExpressionSpecification

      // Unclustered glow (beneath points)
      if (!map.getLayer('unclustered-glow')) {
        map.addLayer({
          id: 'unclustered-glow',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': pointColor,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 5, 10, 10, 15, 16],
            'circle-opacity': 0.28,
            'circle-blur': 0.9,
          },
        })
      }

      // Individual station markers (unclustered)
      if (!map.getLayer('unclustered-point')) {
        map.addLayer({
          id: 'unclustered-point',
          type: 'circle',
          source: 'heatmap-data',
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': pointColor,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 3, 10, 6, 15, 8],
            'circle-stroke-width': 1,
            'circle-stroke-color': isDark
              ? 'rgba(255, 255, 255, 0.65)'
              : 'rgba(255, 255, 255, 0.85)',
          },
        })
      }

      // Keep source in sync in case style was reloaded.
      const src = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
      if (src && geoJsonDataRef.current) {
        src.setData(geoJsonDataRef.current)
      }
    }

    // Setup layers when style loads (fires on initial load and after setStyle)
    map.on('style.load', () => {
      ensureLayers()
      setIsStyleTransitioning(false)
      scheduleHotspotUpdate()
    })

    map.on('load', () => {
      ensureLayers()
      scheduleZoomCallback()
      scheduleHotspotUpdate()
    })

    // Handle zoom changes (debounced to avoid thrashing API calls)
    map.on('zoomend', () => {
      scheduleZoomCallback()
      scheduleHotspotUpdate()
      scheduleViewSave()
    })

    // Persist view position
    map.on('moveend', () => {
      scheduleViewSave()
      scheduleHotspotUpdate()
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
      const cancellationRate = props.cancellation_rate as number
      const delayRate = props.delay_rate as number
      const intensity = (props.intensity as number) ?? 0
      const color = getMarkerColor(intensity)
      const stationName = escapeHtml(String(props.station_name ?? 'Unknown'))

      // Show popup with both metrics
      const isDelaySelected = metricRef.current === 'delays'

      const stationId = escapeHtml(String(props.station_id ?? ''))
      const popupContent = `
        <div class="bv-map-popup">
          <h4 class="bv-map-popup__title">${stationName}</h4>
          <div class="bv-map-popup__rows">
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label ${!isDelaySelected ? 'bv-map-popup__label--active' : ''}">Cancellation Rate:</span>
              <span class="bv-map-popup__value" style="color: ${!isDelaySelected ? color : 'currentColor'}">
                ${(cancellationRate * 100).toFixed(1)}%
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label ${isDelaySelected ? 'bv-map-popup__label--active' : ''}">Delay Rate:</span>
              <span class="bv-map-popup__value" style="color: ${isDelaySelected ? color : 'currentColor'}">
                ${(delayRate * 100).toFixed(1)}%
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Total Departures:</span>
              <span class="bv-map-popup__value">${(props.total_departures as number).toLocaleString()}</span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Cancellations:</span>
              <span class="bv-map-popup__value text-red-600">
                ${(props.cancelled_count as number).toLocaleString()}
              </span>
            </div>
            <div class="bv-map-popup__row">
              <span class="bv-map-popup__label">Delays:</span>
              <span class="bv-map-popup__value text-orange-600">
                ${(props.delayed_count as number).toLocaleString()}
              </span>
            </div>
          </div>
          <a href="/station/${stationId}" class="bv-map-popup__link">
            View Details →
          </a>
        </div>
      `

      popupRef.current?.setLngLat(coordinates).setHTML(popupContent).addTo(map)

      // Notify parent of selection
      onStationSelectRef.current?.(props.station_id as string)
    })

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      popupRef.current?.remove()
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

    mapRef.current = map

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      if (zoomDebounceTimerRef.current) window.clearTimeout(zoomDebounceTimerRef.current)
      if (saveViewTimerRef.current) window.clearTimeout(saveViewTimerRef.current)
      if (hotspotUpdateTimerRef.current) window.clearTimeout(hotspotUpdateTimerRef.current)
      clearHotspotMarkers()
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- geoJsonData accessed via ref; resolvedTheme triggers map recreation
  }, [
    clearHotspotMarkers,
    resolvedTheme,
    scheduleHotspotUpdate,
    scheduleViewSave,
    scheduleZoomCallback,
  ])

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

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-border">
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
  )
}
