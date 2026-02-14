/**
 * Heatmap Controls Component
 * Time range selector and transport mode filters for the heatmap
 */

import { useState, useEffect } from 'react'
import { Check, Clock3, Filter, PauseCircle, RadioTower } from 'lucide-react'
import type { TransportType } from '../../../types/api'
import type { TimeRangePreset, HeatmapEnabledMetrics } from '../../../types/heatmap'
import { TIME_RANGE_LABELS, HEATMAP_METRIC_LABELS } from '../../../types/heatmap'
import { TransportBadge } from '../../shared/Badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../ui/tooltip'
import { Button } from '../../ui/button'

interface HeatmapControlsProps {
  timeRange: TimeRangePreset
  onTimeRangeChange: (range: TimeRangePreset) => void
  selectedTransportModes: TransportType[]
  onTransportModesChange: (modes: TransportType[]) => void
  enabledMetrics: HeatmapEnabledMetrics
  onEnabledMetricsChange: (metrics: HeatmapEnabledMetrics) => void
  autoRefresh: boolean
  onAutoRefreshChange: (live: boolean) => void
  snapshotUpdatedAt?: string
  isLoading?: boolean
}

const TRANSPORT_MODES: { value: TransportType; label: string }[] = [
  { value: 'UBAHN', label: 'U-Bahn' },
  { value: 'SBAHN', label: 'S-Bahn' },
  { value: 'TRAM', label: 'Tram' },
  { value: 'BUS', label: 'Bus' },
  { value: 'BAHN', label: 'Regional' },
]

const TIME_RANGES: TimeRangePreset[] = ['live', '1h', '6h', '24h', '7d', '30d']

export function HeatmapControls({
  timeRange,
  onTimeRangeChange,
  selectedTransportModes,
  onTransportModesChange,
  enabledMetrics,
  onEnabledMetricsChange,
  autoRefresh,
  onAutoRefreshChange,
  snapshotUpdatedAt,
  isLoading = false,
}: HeatmapControlsProps) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(interval)
  }, [])

  const formatLastUpdated = (isoTimestamp: string) => {
    const parsed = Date.parse(isoTimestamp)
    if (Number.isNaN(parsed)) return 'unknown'
    const seconds = Math.floor((now - parsed) / 1000)
    if (seconds < 60) return 'just now'
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ago`
  }

  const toggleTransportMode = (mode: TransportType) => {
    if (selectedTransportModes.includes(mode)) {
      onTransportModesChange(selectedTransportModes.filter(m => m !== mode))
    } else {
      onTransportModesChange([...selectedTransportModes, mode])
    }
  }

  const selectAllModes = () => {
    onTransportModesChange(TRANSPORT_MODES.map(m => m.value))
  }

  const toggleMetric = (metric: keyof HeatmapEnabledMetrics) => {
    const newEnabled = { ...enabledMetrics, [metric]: !enabledMetrics[metric] }
    if (!newEnabled.cancellations && !newEnabled.delays) {
      return
    }
    onEnabledMetricsChange(newEnabled)
  }

  const activeMetricLabels = (
    [
      enabledMetrics.cancellations ? HEATMAP_METRIC_LABELS.cancellations : null,
      enabledMetrics.delays ? HEATMAP_METRIC_LABELS.delays : null,
    ] as const
  ).filter((metric): metric is string => metric !== null)

  const isTransportFiltered =
    selectedTransportModes.length > 0 && selectedTransportModes.length < TRANSPORT_MODES.length
  const activeTransportLabels = TRANSPORT_MODES.filter(mode =>
    selectedTransportModes.includes(mode.value)
  ).map(mode => mode.label)

  const activeFilterChips = [
    `Time: ${TIME_RANGE_LABELS[timeRange]}`,
    `Metrics: ${activeMetricLabels.length > 0 ? activeMetricLabels.join(' + ') : 'None'}`,
    isTransportFiltered ? `Transport: ${activeTransportLabels.join(', ')}` : 'Transport: All types',
    ...(timeRange === 'live' ? [`Refresh: ${autoRefresh ? 'Auto' : 'Paused'}`] : []),
  ]

  return (
    <TooltipProvider delayDuration={300}>
      <div
        className="space-y-4 rounded-md border border-border p-4"
        style={{ backgroundColor: 'hsl(var(--surface) / 0.9)' }}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-h3 text-foreground">Filters</h3>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={autoRefresh ? 'default' : 'outline'}
                size="sm"
                onClick={() => onAutoRefreshChange(!autoRefresh)}
                disabled={isLoading}
                className={autoRefresh ? 'bg-status-healthy hover:bg-status-healthy/90' : ''}
                aria-pressed={autoRefresh}
              >
                {autoRefresh ? (
                  <RadioTower className="h-3.5 w-3.5 animate-pulse" />
                ) : (
                  <PauseCircle className="h-3.5 w-3.5" />
                )}
                <span className="ml-2">{autoRefresh ? 'Auto' : 'Paused'}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{autoRefresh ? 'Auto-refresh enabled' : 'Click to enable auto-refresh'}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {timeRange === 'live' && snapshotUpdatedAt && (
          <div className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-elevated px-3 py-1.5 text-small text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5" />
            Snapshot updated {formatLastUpdated(snapshotUpdatedAt)}
            {autoRefresh && ' • Auto-refresh on'}
          </div>
        )}

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <p className="text-tiny font-semibold uppercase tracking-[0.05em] text-primary">
            Active filters
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {activeFilterChips.map(chip => (
              <span
                key={chip}
                className="inline-flex items-center rounded-md border border-border bg-surface px-2 py-1 text-tiny font-semibold text-foreground"
              >
                {chip}
              </span>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-tiny text-muted-foreground">Time Range</label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {TIME_RANGES.map(range => (
              <Tooltip key={range}>
                <TooltipTrigger asChild>
                  <Button
                    variant={timeRange === range ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => onTimeRangeChange(range)}
                    disabled={isLoading}
                    className={timeRange === range ? '' : 'text-muted-foreground'}
                  >
                    {TIME_RANGE_LABELS[range]}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Show data for {TIME_RANGE_LABELS[range]}</p>
                </TooltipContent>
              </Tooltip>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-tiny text-muted-foreground">Show Metrics</label>
          <div className="flex flex-wrap gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={enabledMetrics.cancellations ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => toggleMetric('cancellations')}
                  disabled={isLoading}
                  className={
                    enabledMetrics.cancellations
                      ? 'bg-status-critical hover:bg-status-critical/90'
                      : 'text-muted-foreground'
                  }
                >
                  <span
                    className={`mr-2 h-2.5 w-2.5 rounded-full ${
                      enabledMetrics.cancellations ? 'bg-white' : 'bg-status-neutral/50'
                    }`}
                  />
                  {HEATMAP_METRIC_LABELS.cancellations}
                  {enabledMetrics.cancellations && <Check className="ml-2 h-3.5 w-3.5" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Toggle cancellation markers on map</p>
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={enabledMetrics.delays ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => toggleMetric('delays')}
                  disabled={isLoading}
                  className={
                    enabledMetrics.delays
                      ? 'bg-status-warning hover:bg-status-warning/90 text-foreground'
                      : 'text-muted-foreground'
                  }
                >
                  <span
                    className={`mr-2 h-2.5 w-2.5 rounded-full ${
                      enabledMetrics.delays ? 'bg-white' : 'bg-status-neutral/50'
                    }`}
                  />
                  {HEATMAP_METRIC_LABELS.delays}
                  {enabledMetrics.delays && <Check className="ml-2 h-3.5 w-3.5" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Toggle delay markers on map</p>
              </TooltipContent>
            </Tooltip>
          </div>
          {enabledMetrics.cancellations && enabledMetrics.delays && (
            <p className="text-small text-muted-foreground">
              Showing combined cancellation &amp; delay intensity
            </p>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="inline-flex items-center gap-1.5 text-tiny text-muted-foreground">
              <Filter className="h-3.5 w-3.5" />
              Transport Types
            </label>
            <Button
              variant="ghost"
              size="sm"
              onClick={selectAllModes}
              disabled={isLoading}
              className="text-primary h-auto p-0 px-1 text-small font-semibold"
            >
              All
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {TRANSPORT_MODES.map(mode => {
              const isSelected =
                selectedTransportModes.length === 0 || selectedTransportModes.includes(mode.value)
              return (
                <Tooltip key={mode.value}>
                  <TooltipTrigger asChild>
                    <Button
                      variant={isSelected ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleTransportMode(mode.value)}
                      disabled={isLoading}
                      className={isSelected ? '' : 'text-muted-foreground'}
                    >
                      <TransportBadge type={mode.value} small />
                      <span className="ml-2">{mode.label}</span>
                      {isSelected && <Check className="ml-2 h-3.5 w-3.5" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Toggle {mode.label} stations</p>
                  </TooltipContent>
                </Tooltip>
              )
            })}
          </div>
          {selectedTransportModes.length === 0 && (
            <p className="text-small text-muted-foreground">Showing all transport types</p>
          )}
        </div>
      </div>
    </TooltipProvider>
  )
}
