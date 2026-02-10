/**
 * Heatmap Page
 * Interactive map visualization of cancellation data across Germany
 */

import { useEffect, useState, lazy, Suspense, useCallback } from 'react'
import { AlertTriangle, Info, Lightbulb } from 'lucide-react'
import { useHeatmapOverview } from '../hooks/useHeatmapOverview'
import { useStationStats } from '../hooks/useStationStats'
import {
  HeatmapControls,
  HeatmapLegend,
  HeatmapOverlayPanel,
  HeatmapStats,
  HeatmapSearchOverlay,
} from '../components/features/heatmap'
import type { TransportType } from '../types/api'
import type { TransitStop } from '../types/gtfs'
import type {
  TimeRangePreset,
  HeatmapEnabledMetrics,
  HeatmapOverviewMetric,
} from '../types/heatmap'
import { HEATMAP_METRIC_LABELS, DEFAULT_ENABLED_METRICS } from '../types/heatmap'
import type { HeatmapMapFocusRequest } from '../components/features/heatmap/MapLibreHeatmap'

// Lazy load the map component to reduce initial bundle size (maplibre-gl is ~1MB)
const CancellationHeatmap = lazy(() =>
  import('../components/features/heatmap/MapLibreHeatmap').then(m => ({
    default: m.MapLibreHeatmap,
  }))
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
    return 'Impact Heatmap'
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
    <div className="flex h-full w-full items-center justify-center rounded-md border border-border bg-surface/85">
      <div className="text-center">
        <div className="mx-auto mb-3 h-10 w-10 animate-spin rounded-full border-2 border-border border-t-primary" />
        <p className="text-small text-muted-foreground">Loading map...</p>
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
  const [focusRequest, setFocusRequest] = useState<HeatmapMapFocusRequest | null>(null)

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

  const handleSearchStationSelect = useCallback((stop: TransitStop) => {
    setFocusRequest({
      requestId: Date.now(),
      stopId: stop.id,
      lat: stop.latitude,
      lon: stop.longitude,
      source: 'search',
      openPopup: false,
    })
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
            focusRequest={focusRequest}
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
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3">
                    <div className="flex items-center gap-2 text-destructive">
                      <AlertTriangle className="h-5 w-5" />
                      <span className="text-small font-semibold">Failed to load heatmap data</span>
                    </div>
                    <p className="mt-1 text-small text-muted-foreground">
                      {error instanceof Error ? error.message : 'An unexpected error occurred'}
                    </p>
                  </div>
                )}

                {!error && !isOverviewLoading && dataPoints.length === 0 && (
                  <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
                    <div className="flex items-center gap-2 text-primary">
                      <Info className="h-5 w-5" />
                      <span className="text-small font-semibold">No data available yet</span>
                    </div>
                    <p className="mt-1 text-small text-muted-foreground">
                      Real-time transit data is being collected. Check back in a few minutes as the
                      system gathers delay and cancellation information from GTFS-RT feeds.
                    </p>
                  </div>
                )}

                <div className="rounded-md border border-border bg-surface-elevated p-3">
                  <h3 className="inline-flex items-center gap-2 text-small font-semibold text-foreground">
                    <Lightbulb className="h-4 w-4 text-primary" />
                    Tips
                  </h3>
                  <ul className="mt-2 space-y-1 text-small text-muted-foreground">
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

                <div className="rounded-md border border-border bg-surface-elevated p-3 text-tiny text-muted-foreground">
                  <p>
                    <strong>Data source:</strong> GTFS schedule data from{' '}
                    <a
                      href="https://gtfs.de"
                      className="underline decoration-dotted underline-offset-2 hover:text-foreground"
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
        <HeatmapSearchOverlay onStationSelect={handleSearchStationSelect} />
      </div>
    </div>
  )
}
