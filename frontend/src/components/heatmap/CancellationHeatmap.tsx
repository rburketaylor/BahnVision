/**
 * Cancellation Heatmap Component
 * Interactive Leaflet map with heatmap overlay for cancellation data
 */

import { useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { HeatmapDataPoint } from '../../types/heatmap'
import { MUNICH_CENTER, DEFAULT_ZOOM, DEFAULT_HEATMAP_CONFIG } from '../../types/heatmap'

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
}

// Custom hook to manage the heat layer
function HeatLayer({ dataPoints }: { dataPoints: HeatmapDataPoint[] }) {
  const map = useMap()
  const heatLayerRef = useRef<L.Layer | null>(null)

  useEffect(() => {
    if (!map) return

    // Remove existing heat layer
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }

    if (dataPoints.length === 0) return

    // Convert data points to heat layer format: [lat, lng, intensity]
    const heatData: [number, number, number][] = dataPoints.map(point => [
      point.latitude,
      point.longitude,
      // Scale intensity: cancellation rate (0-1) scaled for visualization
      // Multiply by 10 to make differences more visible
      Math.min(point.cancellation_rate * 10, 1),
    ])

    // Create heat layer with gradient configuration
    heatLayerRef.current = L.heatLayer(heatData, {
      radius: DEFAULT_HEATMAP_CONFIG.radius,
      blur: DEFAULT_HEATMAP_CONFIG.blur,
      maxZoom: DEFAULT_HEATMAP_CONFIG.maxZoom,
      max: DEFAULT_HEATMAP_CONFIG.max,
      gradient: DEFAULT_HEATMAP_CONFIG.gradient,
    }).addTo(map)

    return () => {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
    }
  }, [map, dataPoints])

  return null
}

// Station markers component
function StationMarkers({
  dataPoints,
  selectedStation: _selectedStation,
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
    if (rate > 0.1) color = '#ef4444' // red
    else if (rate > 0.05) color = '#f97316' // orange
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
                      .filter(([_, stats]) => stats.total > 0)
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
}: CancellationHeatmapProps) {
  if (isLoading) {
    return (
      <div className="w-full h-full min-h-[400px] bg-muted rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Loading heatmap data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full min-h-[400px] rounded-lg overflow-hidden border border-border">
      <MapContainer
        center={MUNICH_CENTER}
        zoom={DEFAULT_ZOOM}
        className="w-full h-full min-h-[400px]"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <HeatLayer dataPoints={dataPoints} />

        <StationMarkers
          dataPoints={dataPoints}
          selectedStation={selectedStation}
          onStationSelect={onStationSelect}
        />
      </MapContainer>
    </div>
  )
}
