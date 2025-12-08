/**
 * Heatmap Page
 * Interactive map visualization of cancellation data across Munich
 */

import { useState } from 'react'
import { useHeatmap } from '../hooks/useHeatmap'
import {
  CancellationHeatmap,
  HeatmapControls,
  HeatmapLegend,
  HeatmapStats,
} from '../components/heatmap'
import type { TransportType } from '../types/api'
import type { TimeRangePreset } from '../types/heatmap'

export default function HeatmapPage() {
  const [timeRange, setTimeRange] = useState<TimeRangePreset>('24h')
  const [transportModes, setTransportModes] = useState<TransportType[]>([])
  const [selectedStation, setSelectedStation] = useState<string | null>(null)
  const [zoom, setZoom] = useState<number>(12) // Default zoom

  const { data, isLoading, error, refetch } = useHeatmap(
    {
      time_range: timeRange,
      transport_modes: transportModes.length > 0 ? transportModes : undefined,
      zoom,
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
            Visualize transit cancellation patterns across Munich
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

      {/* Demo data warning */}
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 mb-4">
        <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span className="font-medium">Demo Data</span>
        </div>
        <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">
          This heatmap is displaying simulated data for demonstration purposes. Real-time data
          integration is planned for a future release.
        </p>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Map - takes up 3/4 of the space on large screens */}
        <div className="lg:col-span-3">
          <div
            className="bg-card rounded-lg border border-border overflow-hidden"
            style={{ height: 'calc(100vh - 18rem)' }}
          >
            <CancellationHeatmap
              dataPoints={dataPoints}
              isLoading={isLoading}
              selectedStation={selectedStation}
              onStationSelect={setSelectedStation}
              onZoomChange={setZoom}
            />
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
          <div className="mt-2 text-xs text-orange-600 dark:text-orange-400 font-medium">
            ⚠️ Currently displaying simulated demo data
          </div>
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

      {/* Data info footer */}
      <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
        <p>
          <strong>Note:</strong> This heatmap shows <strong>simulated demonstration data</strong>{' '}
          for transit services. The current data is generated using a reproducible algorithm based
          on station characteristics and does not reflect real cancellation information. Real-time
          data integration is planned for a future release.
        </p>
      </div>
    </div>
  )
}
