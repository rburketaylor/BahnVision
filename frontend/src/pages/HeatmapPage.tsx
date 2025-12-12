/**
 * Heatmap Page
 * Interactive map visualization of cancellation data across Germany
 */

import { useState, lazy, Suspense } from 'react'
import { useHeatmap } from '../hooks/useHeatmap'
import { HeatmapControls, HeatmapLegend, HeatmapStats } from '../components/heatmap'
import type { TransportType } from '../types/api'
import type { TimeRangePreset } from '../types/heatmap'
import { DEFAULT_ZOOM } from '../types/heatmap'

// Lazy load the map component to reduce initial bundle size (maplibre-gl is ~1MB)
const CancellationHeatmap = lazy(() =>
  import('../components/heatmap/MapLibreHeatmap').then(m => ({ default: m.MapLibreHeatmap }))
)

// Loading skeleton for the map
function MapLoadingSkeleton() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-muted/30 rounded-lg">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">Loading map...</p>
      </div>
    </div>
  )
}

export default function HeatmapPage() {
  const [timeRange, setTimeRange] = useState<TimeRangePreset>('24h')
  const [transportModes, setTransportModes] = useState<TransportType[]>([])
  const [selectedStation, setSelectedStation] = useState<string | null>(null)
  const [zoom, setZoom] = useState<number>(DEFAULT_ZOOM) // Default zoom

  const { data, isLoading, error, refetch } = useHeatmap(
    {
      time_range: timeRange,
      transport_modes: transportModes.length > 0 ? transportModes : undefined,
      zoom: Math.round(zoom), // API requires integer zoom
    },
    { autoRefresh: true }
  )

  const heatmapData = data?.data
  const dataPoints = heatmapData?.data_points ?? []
  const summary = heatmapData?.summary ?? null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Cancellation Heatmap</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Visualize transit cancellation patterns across Germany
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          <svg
            className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center gap-2 text-destructive">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="font-medium">Failed to load heatmap data</span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : 'An unexpected error occurred'}
          </p>
        </div>
      )}


      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Map - takes up 3/4 of the space on large screens */}
        <div className="lg:col-span-3">
          <div
            className="bg-card rounded-lg border border-border overflow-hidden"
            style={{ height: 'calc(100vh - 18rem)' }}
          >
            <Suspense fallback={<MapLoadingSkeleton />}>
              <CancellationHeatmap
                dataPoints={dataPoints}
                isLoading={isLoading}
                selectedStation={selectedStation}
                onStationSelect={setSelectedStation}
                onZoomChange={setZoom}
              />
            </Suspense>
          </div>

          {/* Time range info */}
          {/*
          {heatmapData?.time_range && (
            <div className="mt-2 text-xs text-muted-foreground">
              Data from{' '}
              <span className="font-medium">
                {new Date(heatmapData.time_range.from).toLocaleString()}
              </span>{' '}
              to{' '}
              <span className="font-medium">
                {new Date(heatmapData.time_range.to).toLocaleString()}
              </span>
            </div>
          )}
          */}

        </div>

        {/* Sidebar - controls, legend, and stats */}
        <div className="lg:col-span-1 space-y-4">
          <HeatmapControls
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
            selectedTransportModes={transportModes}
            onTransportModesChange={setTransportModes}
            isLoading={isLoading}
          />

          <HeatmapLegend />

          <HeatmapStats summary={summary} isLoading={isLoading} />
        </div>
      </div>

      {/* Data source footer */}
      <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
        <p>
          <strong>Data source:</strong> GTFS schedule data from{' '}
          <a href="https://gtfs.de" className="underline hover:text-foreground" target="_blank" rel="noopener noreferrer">gtfs.de</a>.
          Updated daily.
        </p>
      </div>
    </div>
  )
}
