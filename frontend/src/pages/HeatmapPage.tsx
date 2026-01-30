/**
 * Heatmap Page
 * Interactive map visualization of cancellation data across Germany
 */

import { useEffect, useState, lazy, Suspense, useCallback } from 'react'
import { useHeatmapOverview } from '../hooks/useHeatmapOverview'
import { useStationStats } from '../hooks/useStationStats'
import {
  HeatmapControls,
  HeatmapLegend,
  HeatmapOverlayPanel,
  HeatmapStats,
  HeatmapSearchOverlay,
} from '../components/heatmap'
import type { TransportType } from '../types/api'
import type {
  TimeRangePreset,
  HeatmapEnabledMetrics,
  HeatmapOverviewMetric,
} from '../types/heatmap'
import { HEATMAP_METRIC_LABELS, DEFAULT_ENABLED_METRICS } from '../types/heatmap'

// Lazy load the map component to reduce initial bundle size (maplibre-gl is ~1MB)
const CancellationHeatmap = lazy(() =>
  import('../components/heatmap/MapLibreHeatmap').then(m => ({ default: m.MapLibreHeatmap }))
)

const CONTROLS_OPEN_STORAGE_KEY = 'bahnvision-heatmap-controls-open-v1'

function isTypingTarget(target: EventTarget | null) {
  if (!target) return false
  if (target instanceof HTMLInputElement) return true
  if (target instanceof HTMLTextAreaElement) return true
  if (target instanceof HTMLSelectElement) return true
  if (target instanceof HTMLElement && target.isContentEditable) return true
  return false
}

// Helper to generate title based on enabled metrics
function getHeatmapTitle(enabledMetrics: HeatmapEnabledMetrics): string {
  if (enabledMetrics.cancellations && enabledMetrics.delays) {
    return 'Combined Impact Heatmap'
  }
  if (enabledMetrics.cancellations) {
    return `${HEATMAP_METRIC_LABELS.cancellations} Heatmap`
  }
  if (enabledMetrics.delays) {
    return `${HEATMAP_METRIC_LABELS.delays} Heatmap`
  }
  return 'Heatmap'
}

// Helper to generate description based on enabled metrics
function getHeatmapDescription(enabledMetrics: HeatmapEnabledMetrics): string {
  if (enabledMetrics.cancellations && enabledMetrics.delays) {
    return 'Visualize combined cancellation and delay patterns across Germany'
  }
  if (enabledMetrics.cancellations) {
    return 'Visualize transit cancellation patterns across Germany'
  }
  if (enabledMetrics.delays) {
    return 'Visualize transit delay patterns across Germany'
  }
  return 'Enable at least one metric to view heatmap'
}

function toOverviewMetric(enabledMetrics: HeatmapEnabledMetrics): HeatmapOverviewMetric {
  if (enabledMetrics.cancellations && enabledMetrics.delays) return 'both'
  if (enabledMetrics.delays) return 'delays'
  return 'cancellations'
}

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
  const [timeRange, setTimeRange] = useState<TimeRangePreset>('live')
  const [transportModes, setTransportModes] = useState<TransportType[]>([])
  const [enabledMetrics, setEnabledMetrics] = useState<HeatmapEnabledMetrics>(() => ({
    ...DEFAULT_ENABLED_METRICS,
  }))
  const [controlsOpen, setControlsOpen] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null)

  // Fetch lightweight overview (all stations)
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error,
    refetch,
  } = useHeatmapOverview(
    {
      time_range: timeRange,
      transport_modes: transportModes.length > 0 ? transportModes : undefined,
      metrics: toOverviewMetric(enabledMetrics),
    },
    { autoRefresh }
  )

  // Map TimeRangePreset to StationStatsTimeRange (live -> 24h since station stats doesn't support live)
  const stationStatsTimeRange = timeRange === 'live' ? '24h' : timeRange

  // Fetch details on-demand when station is selected
  const { data: stationStats, isLoading: isStationStatsLoading } = useStationStats(
    selectedStationId ?? undefined,
    stationStatsTimeRange,
    {
      enabled: !!selectedStationId,
      // The popup doesn't use network averages, and they can be very expensive for long ranges (7d/30d).
      includeNetworkAverages: false,
    }
  )

  const handleStationDetailRequested = useCallback((stationId: string) => {
    setSelectedStationId(stationId)
  }, [])

  const dataPoints = overviewData?.points ?? []
  const heatmapSummary = overviewData?.summary ?? null
  const snapshotUpdatedAt = overviewData?.last_updated_at

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(CONTROLS_OPEN_STORAGE_KEY)
      if (stored === '0') setControlsOpen(false)
      if (stored === '1') setControlsOpen(true)
    } catch {
      // Ignore storage errors (private mode / disabled storage)
    }
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(CONTROLS_OPEN_STORAGE_KEY, controlsOpen ? '1' : '0')
    } catch {
      // Ignore storage errors (private mode / disabled storage)
    }
  }, [controlsOpen])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return

      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault()
        setControlsOpen(open => !open)
        return
      }

      if (e.key === 'Escape' && controlsOpen) {
        e.preventDefault()
        setControlsOpen(false)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [controlsOpen])

  return (
    <div className="fixed inset-x-0 top-16 bottom-0" data-testid="heatmap-container">
      <div className="relative w-full h-full overflow-hidden p-2 sm:p-3">
        <Suspense fallback={<MapLoadingSkeleton />}>
          <CancellationHeatmap
            overviewPoints={dataPoints}
            isLoading={isOverviewLoading}
            enabledMetrics={enabledMetrics}
            onStationDetailRequested={handleStationDetailRequested}
            onStationSelect={setSelectedStationId}
            selectedStationId={selectedStationId}
            stationStats={stationStats ?? null}
            isStationStatsLoading={isStationStatsLoading}
            overlay={
              <HeatmapOverlayPanel
                open={controlsOpen}
                onOpenChange={setControlsOpen}
                title={getHeatmapTitle(enabledMetrics)}
                description={getHeatmapDescription(enabledMetrics)}
                hasError={Boolean(error)}
                isLoading={isOverviewLoading}
                onRefresh={() => refetch()}
              >
                {error && (
                  <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-destructive">
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <span className="text-sm font-medium">Failed to load heatmap data</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {error instanceof Error ? error.message : 'An unexpected error occurred'}
                    </p>
                  </div>
                )}

                {!error && !isOverviewLoading && dataPoints.length === 0 && (
                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <span className="text-sm font-medium">No data available yet</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Real-time transit data is being collected. Check back in a few minutes as the
                      system gathers delay and cancellation information from GTFS-RT feeds.
                    </p>
                  </div>
                )}

                <div className="bg-muted/40 rounded-lg border border-border/60 p-3">
                  <h3 className="text-xs font-semibold text-foreground">Tips</h3>
                  <ul className="mt-2 text-xs text-muted-foreground space-y-1">
                    <li>Click a station dot to see details.</li>
                    <li>Click a cluster to zoom in.</li>
                    <li>Use "Reset view" to return to Germany.</li>
                  </ul>
                </div>

                <HeatmapControls
                  timeRange={timeRange}
                  onTimeRangeChange={setTimeRange}
                  selectedTransportModes={transportModes}
                  onTransportModesChange={setTransportModes}
                  enabledMetrics={enabledMetrics}
                  onEnabledMetricsChange={setEnabledMetrics}
                  autoRefresh={autoRefresh}
                  onAutoRefreshChange={setAutoRefresh}
                  snapshotUpdatedAt={snapshotUpdatedAt}
                  isLoading={isOverviewLoading}
                />

                <HeatmapLegend enabledMetrics={enabledMetrics} />

                <HeatmapStats
                  summary={heatmapSummary}
                  isLoading={isOverviewLoading}
                  enabledMetrics={enabledMetrics}
                />

                <div className="text-[11px] text-muted-foreground bg-muted/50 rounded-lg p-3">
                  <p>
                    <strong>Data source:</strong> GTFS schedule data from{' '}
                    <a
                      href="https://gtfs.de"
                      className="underline hover:text-foreground"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      gtfs.de
                    </a>
                    . Updated daily.
                  </p>
                </div>
              </HeatmapOverlayPanel>
            }
          />
        </Suspense>
        <HeatmapSearchOverlay />
      </div>
    </div>
  )
}
