/**
 * Cancellation Heatmap Component
 * Interactive Leaflet map with heatmap overlay for cancellation data
 *
 * Layer Configuration:
 * - Base Layers: Multiple map styles (CartoDB Voyager, Positron, OSM, OPNVKarte)
 * - Overlay Layers: Railway infrastructure overlay (OpenRailwayMap)
 * - Heat Layer: Cancellation data visualization
 * - Station Markers: Individual station markers with cancellation info
 *
 * Z-Index Hierarchy:
 * - Base Maps: 1-100 (automatic)
 * - Railway Overlay: 500
 * - Heat Layer: 400
 * - Station Markers: 1000+
 */

import { useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap, LayersControl } from 'react-leaflet'
import L from 'leaflet'
// CSS is imported in main.tsx

import type { HeatmapDataPoint } from '../../types/heatmap'
import { MUNICH_CENTER, DEFAULT_ZOOM } from '../../types/heatmap'

// Map tile layer configurations
const MAP_LAYERS = {
  // CartoDB Voyager - clean map with good visibility of streets and areas
  cartoVoyager: {
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  // CartoDB Positron - light theme, good for overlays
  cartoPositron: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  // OpenStreetMap standard
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  // ÖPNVKarte - German public transport map
  opnvkarte: {
    url: 'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="https://memomaps.de/">memomaps.de</a>',
  },
  // OpenRailwayMap overlay - shows rail infrastructure
  // Note: OpenRailwayMap does NOT support {s} subdomains
  openRailwayMap: {
    url: 'https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="https://www.openrailwaymap.org/">OpenRailwayMap</a>',
  },
}

// Import leaflet.heat - it adds L.heatLayer
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - leaflet.heat has no types
import 'leaflet.heat'

// Extend Leaflet types for heat layer
declare module 'leaflet' {
  function heatLayer(
    latlngs: [number, number, number][],
    options?: {
      radius?: number
      blur?: number
      maxZoom?: number
      max?: number
      gradient?: Record<number, string>
    }
  ): L.Layer
}

// Fix default marker icons in Leaflet with Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// @ts-expect-error - Leaflet icon fix
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

interface CancellationHeatmapProps {
  dataPoints: HeatmapDataPoint[]
  isLoading?: boolean
  selectedStation?: string | null
  onStationSelect?: (stationId: string | null) => void
  onZoomChange?: (zoom: number) => void
}

// Custom hook to track zoom changes
function ZoomTracker({ onZoomChange }: { onZoomChange?: (zoom: number) => void }) {
  const map = useMap()

  useEffect(() => {
    if (!map || !onZoomChange) return

    const handleZoom = () => {
      onZoomChange(map.getZoom())
    }

    // Report initial zoom
    onZoomChange(map.getZoom())

    map.on('zoomend', handleZoom)

    return () => {
      map.off('zoomend', handleZoom)
    }
  }, [map, onZoomChange])

  return null
}

// Custom hook to manage the heat layer
function HeatLayer({ dataPoints }: { dataPoints: HeatmapDataPoint[] }) {
  const map = useMap()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const heatLayerRef = useRef<any>(null)
  const processedDataCache = useRef<Map<string, [number, number, number][]>>(new Map())
  const debouncedUpdateRef = useRef<number | null>(null)

  // Dynamic heat layer configuration based on zoom
  const getHeatLayerOptions = (zoom: number) => {
    const radius = zoom < 10 ? 30 : zoom < 12 ? 20 : 15
    const blur = zoom < 10 ? 20 : zoom < 12 ? 15 : 10

    return {
      radius,
      blur,
      maxZoom: 17,
      max: 1.0,
      gradient: {
        0.0: 'rgba(0, 255, 0, 0)',
        0.2: 'rgba(0, 255, 0, 0.5)',
        0.4: 'yellow',
        0.6: 'orange',
        0.8: 'red',
        1.0: 'darkred',
      },
    }
  }

  // Pre-process and cache data by zoom range to avoid redundant calculations
  const getProcessedData = (zoom: number): [number, number, number][] => {
    const zoomRange = zoom < 10 ? 'low' : zoom < 12 ? 'medium' : 'high'
    const cacheKey = `${zoomRange}-${dataPoints.length}`

    if (!processedDataCache.current.has(cacheKey)) {
      const intensityMultiplier = zoom < 12 ? 10 : 8
      const processed: [number, number, number][] = dataPoints.map(point => [
        point.latitude,
        point.longitude,
        Math.min(point.cancellation_rate * intensityMultiplier, 1),
      ])
      processedDataCache.current.set(cacheKey, processed)
    }

    return processedDataCache.current.get(cacheKey)!
  }

  // Efficient heat layer update - only updates existing layer instead of recreating
  const updateHeatLayer = () => {
    if (dataPoints.length === 0) {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
      return
    }

    const zoom = map.getZoom()
    const options = getHeatLayerOptions(zoom)
    const processedData = getProcessedData(zoom)

    if (!heatLayerRef.current) {
      // Create new layer only if it doesn't exist
      heatLayerRef.current = L.heatLayer(processedData, options).addTo(map)
      if (heatLayerRef.current.setZIndex) {
        heatLayerRef.current.setZIndex(400)
      }
    } else {
      // Update existing layer efficiently
      heatLayerRef.current.setLatLngs(processedData)
      heatLayerRef.current.setOptions(options)
    }
  }

  useEffect(() => {
    if (!map) return

    // Initial creation
    updateHeatLayer()

    // Debounced zoom handler to prevent excessive updates during smooth zoom animations
    const handleZoom = () => {
      if (debouncedUpdateRef.current) {
        clearTimeout(debouncedUpdateRef.current)
      }
      debouncedUpdateRef.current = setTimeout(() => {
        updateHeatLayer()
      }, 150) // 150ms debounce
    }

    map.on('zoomend', handleZoom)

    return () => {
      map.off('zoomend', handleZoom)
      if (debouncedUpdateRef.current) {
        clearTimeout(debouncedUpdateRef.current)
      }
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
      // Clear cache on unmount to prevent memory leaks
      processedDataCache.current.clear()
    }
  }, [map, dataPoints])

  return null
}

// Station markers component
function StationMarkers({
  dataPoints,
  onStationSelect,
}: {
  dataPoints: HeatmapDataPoint[]
  selectedStation?: string | null
  onStationSelect?: (stationId: string | null) => void
}) {
  // Only show markers for stations with notable cancellation rates
  const notableStations = useMemo(
    () => dataPoints.filter(p => p.cancellation_rate > 0.03 && p.total_departures >= 50),
    [dataPoints]
  )

  // Custom icon based on cancellation severity
  const getMarkerIcon = (rate: number) => {
    let color = '#22c55e' // green
    if (rate > 0.1)
      color = '#ef4444' // red
    else if (rate > 0.05)
      color = '#f97316' // orange
    else if (rate > 0.03) color = '#eab308' // yellow

    return L.divIcon({
      className: 'custom-marker',
      html: `<div style="
        width: 12px;
        height: 12px;
        background-color: ${color};
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      "></div>`,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    })
  }

  const formatPercent = (rate: number) => `${(rate * 100).toFixed(1)}%`

  return (
    <>
      {notableStations.map(station => (
        <Marker
          key={station.station_id}
          position={[station.latitude, station.longitude]}
          icon={getMarkerIcon(station.cancellation_rate)}
          zIndexOffset={1000} // Ensure markers appear above heat layer
          eventHandlers={{
            click: () => onStationSelect?.(station.station_id),
          }}
        >
          <Popup>
            <div className="min-w-[200px]">
              <h4 className="font-semibold text-gray-900 mb-2">{station.station_name}</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Cancellation Rate:</span>
                  <span
                    className={`font-medium ${
                      station.cancellation_rate > 0.05 ? 'text-red-600' : 'text-orange-600'
                    }`}
                  >
                    {formatPercent(station.cancellation_rate)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Departures:</span>
                  <span className="font-medium">{station.total_departures.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Cancellations:</span>
                  <span className="font-medium text-red-600">
                    {station.cancelled_count.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Transport breakdown */}
              {Object.keys(station.by_transport).length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-1">By Transport Type:</p>
                  <div className="space-y-1">
                    {Object.entries(station.by_transport)
                      .filter(([, stats]) => stats.total > 0)
                      .sort((a, b) => b[1].cancelled - a[1].cancelled)
                      .slice(0, 3)
                      .map(([type, stats]) => (
                        <div key={type} className="flex justify-between text-xs">
                          <span className="text-gray-600">{type}:</span>
                          <span>
                            {stats.cancelled}/{stats.total}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </>
  )
}

export function CancellationHeatmap({
  dataPoints,
  isLoading = false,
  selectedStation,
  onStationSelect,
  onZoomChange,
}: CancellationHeatmapProps) {
  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-border">
      <MapContainer
        center={MUNICH_CENTER}
        zoom={DEFAULT_ZOOM}
        className="absolute inset-0 z-0"
        style={{ width: '100%', height: '100%' }}
        scrollWheelZoom={true}
      >
        {/* Default base layer - ensures map is always visible */}
        <TileLayer
          attribution={MAP_LAYERS.cartoVoyager.attribution}
          url={MAP_LAYERS.cartoVoyager.url}
          maxZoom={19}
        />

        {/* Layer control for switching map styles and overlays */}
        <LayersControl position="topright">
          {/* Alternative base layers for switching */}
          <LayersControl.BaseLayer name="CartoDB Positron">
            <TileLayer
              attribution={MAP_LAYERS.cartoPositron.attribution}
              url={MAP_LAYERS.cartoPositron.url}
              maxZoom={19}
            />
          </LayersControl.BaseLayer>

          <LayersControl.BaseLayer name="OpenStreetMap">
            <TileLayer
              attribution={MAP_LAYERS.osm.attribution}
              url={MAP_LAYERS.osm.url}
              maxZoom={19}
            />
          </LayersControl.BaseLayer>

          <LayersControl.BaseLayer name="ÖPNVKarte (German Transport)">
            <TileLayer
              attribution={MAP_LAYERS.opnvkarte.attribution}
              url={MAP_LAYERS.opnvkarte.url}
              maxZoom={18}
            />
          </LayersControl.BaseLayer>

          {/* Overlay layers - can be toggled independently */}
          <LayersControl.Overlay name="Railway Infrastructure" checked>
            <TileLayer
              attribution={MAP_LAYERS.openRailwayMap.attribution}
              url={MAP_LAYERS.openRailwayMap.url}
              maxZoom={18}
              opacity={0.7}
              zIndex={500} // Ensure railway overlay appears above base map but below markers
            />
          </LayersControl.Overlay>
        </LayersControl>

        <ZoomTracker onZoomChange={onZoomChange} />

        <HeatLayer dataPoints={dataPoints} />

        <StationMarkers
          dataPoints={dataPoints}
          selectedStation={selectedStation}
          onStationSelect={onStationSelect}
        />
      </MapContainer>

      {/* Loading overlay - shown while keeping the map rendered */}
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
