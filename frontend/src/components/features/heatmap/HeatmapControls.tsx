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
    <div
      className="space-y-4 rounded-md border border-border p-4"
      style={{ backgroundColor: 'hsl(var(--surface) / 0.9)' }}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-h3 text-foreground">Filters</h3>
        <button
          onClick={() => onAutoRefreshChange(!autoRefresh)}
          disabled={isLoading}
          className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-small font-semibold uppercase tracking-[0.05em] ${
            autoRefresh
              ? 'border-status-healthy/45 bg-status-healthy/12 text-status-healthy ring-1 ring-status-healthy/35'
              : 'border-border bg-surface-elevated text-muted-foreground'
          } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
          aria-pressed={autoRefresh}
          title={autoRefresh ? 'Auto-refresh enabled' : 'Click to enable auto-refresh'}
        >
          {autoRefresh ? (
            <RadioTower className="h-3.5 w-3.5 animate-status-pulse" />
          ) : (
            <PauseCircle className="h-3.5 w-3.5" />
          )}
          {autoRefresh ? 'Auto-refresh' : 'Paused'}
        </button>
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
            <button
              key={range}
              onClick={() => onTimeRangeChange(range)}
              disabled={isLoading}
              className={`btn-bvv rounded-md border px-2.5 py-2 text-small font-semibold ${
                timeRange === range
                  ? 'border-primary/50 bg-primary/15 text-primary ring-1 ring-primary/35 shadow-sm'
                  : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated hover:text-foreground'
              } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
            >
              {TIME_RANGE_LABELS[range]}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-tiny text-muted-foreground">Show Metrics</label>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => toggleMetric('cancellations')}
            disabled={isLoading}
            className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-small font-semibold ${
              enabledMetrics.cancellations
                ? 'border-status-critical/45 bg-status-critical/12 text-status-critical ring-1 ring-status-critical/35 shadow-sm'
                : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated hover:text-foreground'
            } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
            aria-pressed={enabledMetrics.cancellations}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                enabledMetrics.cancellations ? 'bg-status-critical' : 'bg-status-neutral/50'
              }`}
            />
            {HEATMAP_METRIC_LABELS.cancellations}
            {enabledMetrics.cancellations && <Check className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={() => toggleMetric('delays')}
            disabled={isLoading}
            className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-small font-semibold ${
              enabledMetrics.delays
                ? 'border-status-warning/45 bg-status-warning/12 text-status-warning ring-1 ring-status-warning/35 shadow-sm'
                : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated hover:text-foreground'
            } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
            aria-pressed={enabledMetrics.delays}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                enabledMetrics.delays ? 'bg-status-warning' : 'bg-status-neutral/50'
              }`}
            />
            {HEATMAP_METRIC_LABELS.delays}
            {enabledMetrics.delays && <Check className="h-3.5 w-3.5" />}
          </button>
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
          <button
            onClick={selectAllModes}
            disabled={isLoading}
            className="btn-bvv text-small font-semibold text-primary hover:text-primary/80 disabled:opacity-50"
          >
            All
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {TRANSPORT_MODES.map(mode => {
            const isSelected =
              selectedTransportModes.length === 0 || selectedTransportModes.includes(mode.value)
            return (
              <button
                key={mode.value}
                onClick={() => toggleTransportMode(mode.value)}
                disabled={isLoading}
                className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 ${
                  isSelected
                    ? 'border-primary/50 bg-primary/15 text-foreground ring-1 ring-primary/35 shadow-sm'
                    : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated'
                } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
                aria-label={`Toggle ${mode.label}`}
                aria-pressed={isSelected}
              >
                <TransportBadge type={mode.value} small />
                <span className="text-small font-semibold">{mode.label}</span>
                {isSelected && <Check className="h-3.5 w-3.5 text-primary/80" />}
              </button>
            )
          })}
        </div>
        {selectedTransportModes.length === 0 && (
          <p className="text-small text-muted-foreground">Showing all transport types</p>
        )}
      </div>
    </div>
  )
}
