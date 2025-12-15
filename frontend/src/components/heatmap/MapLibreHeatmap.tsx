/**
 * MapLibre Heatmap Component
 * Interactive MapLibre GL JS map with heatmap overlay for cancellation data
 *
 * Features:
 * - Vector tiles from OpenFreeMap (no API key required)
 * - Native MapLibre heatmap layer (WebGL-based)
 * - GeoJSON clustering for station markers
 * - Smooth zoom and pan
 */

import { useEffect, useRef, useCallback, useMemo } from 'react'
import maplibregl from 'maplibre-gl'
import type { HeatmapDataPoint } from '../../types/heatmap'
import { GERMANY_CENTER, DEFAULT_ZOOM } from '../../types/heatmap'

// OpenFreeMap style URL - free vector tiles, no API key needed
const OPENFREEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

interface MapLibreHeatmapProps {
  dataPoints: HeatmapDataPoint[]
  isLoading?: boolean
  selectedStation?: string | null
  onStationSelect?: (stationId: string | null) => void
  onZoomChange?: (zoom: number) => void
}

/**
 * Convert HeatmapDataPoint array to GeoJSON FeatureCollection
 * Note: GeoJSON uses [lng, lat] order, opposite of Leaflet's [lat, lng]
 */
function toGeoJSON(dataPoints: HeatmapDataPoint[]): GeoJSON.FeatureCollection {
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
    features: validPoints.map(point => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [point.longitude, point.latitude], // [lng, lat] for GeoJSON
      },
      properties: {
        station_id: point.station_id ?? '',
        station_name: point.station_name ?? 'Unknown',
        cancellation_rate: point.cancellation_rate ?? 0,
        total_departures: point.total_departures ?? 0,
        cancelled_count: point.cancelled_count ?? 0,
        // Pre-calculate intensity for heatmap (0-1 scale)
        intensity: Math.min((point.cancellation_rate ?? 0) * 10, 1),
      },
    })),
  }
}

/**
 * Get marker color based on cancellation severity
 */
function getMarkerColor(rate: number): string {
  if (rate > 0.1) return '#ef4444' // red
  if (rate > 0.05) return '#f97316' // orange
  if (rate > 0.03) return '#eab308' // yellow
  return '#22c55e' // green
}

export function MapLibreHeatmap({
  dataPoints,
  isLoading = false,
  onStationSelect,
  onZoomChange,
}: MapLibreHeatmapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)

  // Memoize GeoJSON conversion to avoid recalculating on every render
  const geoJsonData = useMemo(() => toGeoJSON(dataPoints), [dataPoints])

  // Update map data when dataPoints change
  const updateMapData = useCallback(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const source = map.getSource('heatmap-data') as maplibregl.GeoJSONSource | undefined
    if (source) {
      source.setData(geoJsonData)
    }
  }, [geoJsonData])

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: OPENFREEMAP_STYLE,
      center: [GERMANY_CENTER[1], GERMANY_CENTER[0]], // [lng, lat] for MapLibre
      zoom: DEFAULT_ZOOM,
    })

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    // Create popup instance for reuse
    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '300px',
    })

    // Setup layers when style loads
    map.on('load', () => {
      // Add GeoJSON source for heatmap and markers
      map.addSource('heatmap-data', {
        type: 'geojson',
        data: geoJsonData,
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      })

      // Heatmap layer
      map.addLayer({
        id: 'heatmap-layer',
        type: 'heatmap',
        source: 'heatmap-data',
        maxzoom: 15,
        paint: {
          // Weight based on pre-calculated intensity
          'heatmap-weight': ['get', 'intensity'],
          // Increase intensity as zoom level increases
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
          // Color gradient from green (low) to red (high)
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(0, 255, 0, 0)',
            0.2,
            'rgba(0, 255, 0, 0.5)',
            0.4,
            'rgba(255, 255, 0, 0.7)',
            0.6,
            'rgba(255, 165, 0, 0.8)',
            0.8,
            'rgba(255, 0, 0, 0.9)',
            1,
            'rgba(139, 0, 0, 1)',
          ],
          // Radius increases with zoom
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 20],
          // Fade out at higher zoom levels where points are visible
          'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 12, 1, 15, 0],
        },
      })

      // Cluster circles
      map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'heatmap-data',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#51bbd6', // < 10 points
            10,
            '#f1f075', // 10-50 points
            50,
            '#f28cb1', // 50+ points
          ],
          'circle-radius': ['step', ['get', 'point_count'], 15, 10, 20, 50, 25],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff',
        },
      })

      // Cluster count labels
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
          'text-color': '#333',
        },
      })

      // Individual station markers (unclustered)
      map.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: 'heatmap-data',
        filter: ['!', ['has', 'point_count']],
        minzoom: 10, // Only show at higher zoom levels
        paint: {
          'circle-color': [
            'case',
            ['>', ['get', 'cancellation_rate'], 0.1],
            '#ef4444',
            ['>', ['get', 'cancellation_rate'], 0.05],
            '#f97316',
            ['>', ['get', 'cancellation_rate'], 0.03],
            '#eab308',
            '#22c55e',
          ],
          'circle-radius': 8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff',
        },
      })
    })

    // Handle zoom changes
    map.on('zoomend', () => {
      onZoomChange?.(map.getZoom())
    })

    // Report initial zoom
    map.on('load', () => {
      onZoomChange?.(map.getZoom())
    })

    // Click on cluster to zoom in
    map.on('click', 'clusters', (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })
      if (!features.length) return

      const clusterId = features[0].properties?.cluster_id as number
      const source = map.getSource('heatmap-data') as maplibregl.GeoJSONSource
      source.getClusterExpansionZoom(clusterId).then(zoom => {
        if (zoom === undefined) return
        const geometry = features[0].geometry
        if (geometry.type === 'Point') {
          map.easeTo({
            center: geometry.coordinates as [number, number],
            zoom: zoom,
          })
        }
      })
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
      const rate = props.cancellation_rate as number
      const color = getMarkerColor(rate)

      // Show popup
      const popupContent = `
        <div class="min-w-[200px] p-2">
          <h4 class="font-semibold text-gray-900 mb-2">${props.station_name}</h4>
          <div class="space-y-1 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">Cancellation Rate:</span>
              <span class="font-medium" style="color: ${color}">
                ${(rate * 100).toFixed(1)}%
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Total Departures:</span>
              <span class="font-medium">${(props.total_departures as number).toLocaleString()}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Cancellations:</span>
              <span class="font-medium text-red-600">
                ${(props.cancelled_count as number).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      `

      popupRef.current?.setLngLat(coordinates).setHTML(popupContent).addTo(map)

      // Notify parent of selection
      onStationSelect?.(props.station_id as string)
    })

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
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Update data when dataPoints change
  useEffect(() => {
    updateMapData()
  }, [updateMapData])

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-border">
      <div ref={mapContainerRef} className="absolute inset-0 z-0" />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 bg-background/50 z-[1000] flex items-center justify-center">
          <div className="text-center bg-card p-4 rounded-lg shadow-lg">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Loading heatmap data...</p>
          </div>
        </div>
      )}
    </div>
  )
}
