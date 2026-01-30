/**
 * Heatmap Controls Component
 * Time range selector and transport mode filters for the heatmap
 * BVV-styled with circular badges, toggle switches, and pill selectors
 */

import { useState, useEffect } from 'react'
import type { TransportType } from '../../types/api'
import type { TimeRangePreset, HeatmapEnabledMetrics } from '../../types/heatmap'
import { TIME_RANGE_LABELS, HEATMAP_METRIC_LABELS } from '../../types/heatmap'
import { TransportBadge } from '../shared/Badge'

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

const TRANSPORT_MODES: { value: TransportType; label: string; color: string }[] = [
  { value: 'UBAHN', label: 'U-Bahn', color: 'bg-ubahn' },
  { value: 'SBAHN', label: 'S-Bahn', color: 'bg-sbahn' },
  { value: 'TRAM', label: 'Tram', color: 'bg-tram' },
  { value: 'BUS', label: 'Bus', color: 'bg-bus' },
  { value: 'BAHN', label: 'Regional', color: 'bg-gray-600' },
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
  // Track current time for relative time display (updates every 30s)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(interval)
  }, [])

  // Format last updated time as relative time
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
    // Don't allow both to be disabled
    const newEnabled = { ...enabledMetrics, [metric]: !enabledMetrics[metric] }
    if (!newEnabled.cancellations && !newEnabled.delays) {
      return // Keep at least one enabled
    }
    onEnabledMetricsChange(newEnabled)
  }

  return (
    <div className="bg-card rounded-lg border border-border p-4 space-y-4">
      {/* Live Mode Toggle */}
      <div className="flex items-center justify-between">
        <h3 className="text-h3 text-foreground">Filters</h3>
        <button
          onClick={() => onAutoRefreshChange(!autoRefresh)}
          disabled={isLoading}
          className={`btn-bvv flex items-center gap-2 px-3 py-1.5 rounded-full text-small font-medium transition-colors ${
            autoRefresh
              ? 'bg-status-healthy/20 text-status-healthy border border-status-healthy/40'
              : 'bg-muted text-muted hover:bg-muted/80 border border-transparent'
          } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          aria-pressed={autoRefresh}
          title={autoRefresh ? 'Auto-refresh enabled' : 'Click to enable auto-refresh'}
        >
          <span
            className={`w-2 h-2 rounded-full transition-all ${
              autoRefresh ? 'bg-status-healthy animate-pulse' : 'bg-muted-foreground/30'
            }`}
          />
          {autoRefresh ? 'Auto-refresh' : 'Paused'}
        </button>
      </div>

      {/* Last Updated Info */}
      {timeRange === 'live' && snapshotUpdatedAt && (
        <div className="text-small text-muted bg-muted/30 rounded-full px-3 py-1.5 text-center">
          Snapshot updated {formatLastUpdated(snapshotUpdatedAt)}
          {autoRefresh && ' • Auto-refresh on'}
        </div>
      )}

      {/* Time Range Selection - Pill shaped */}
      <div className="space-y-2">
        <label className="text-small font-medium text-muted">Time Range</label>
        <div className="flex flex-wrap gap-2">
          {TIME_RANGES.map(range => (
            <button
              key={range}
              onClick={() => onTimeRangeChange(range)}
              disabled={isLoading}
              className={`btn-bvv px-3 py-1.5 rounded-full text-small font-medium transition-colors ${
                timeRange === range
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted hover:bg-muted/80'
              } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {TIME_RANGE_LABELS[range]}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Toggles */}
      <div className="space-y-2">
        <label className="text-small font-medium text-muted">Show Metrics</label>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => toggleMetric('cancellations')}
            disabled={isLoading}
            className={`btn-bvv flex items-center gap-2 px-3 py-1.5 rounded-full text-small font-medium transition-colors ${
              enabledMetrics.cancellations
                ? 'bg-status-critical/20 text-status-critical border border-status-critical/40'
                : 'bg-muted text-muted hover:bg-muted/80 border border-transparent'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            aria-pressed={enabledMetrics.cancellations}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                enabledMetrics.cancellations ? 'bg-status-critical' : 'bg-muted-foreground/30'
              }`}
            />
            {HEATMAP_METRIC_LABELS.cancellations}
          </button>
          <button
            onClick={() => toggleMetric('delays')}
            disabled={isLoading}
            className={`btn-bvv flex items-center gap-2 px-3 py-1.5 rounded-full text-small font-medium transition-colors ${
              enabledMetrics.delays
                ? 'bg-status-warning/20 text-status-warning border border-status-warning/40'
                : 'bg-muted text-muted hover:bg-muted/80 border border-transparent'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            aria-pressed={enabledMetrics.delays}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                enabledMetrics.delays ? 'bg-status-warning' : 'bg-muted-foreground/30'
              }`}
            />
            {HEATMAP_METRIC_LABELS.delays}
          </button>
        </div>
        {enabledMetrics.cancellations && enabledMetrics.delays && (
          <p className="text-small text-muted italic">
            Showing combined cancellation &amp; delay intensity
          </p>
        )}
      </div>

      {/* Transport Mode Filters - Circular badges */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-small font-medium text-muted">Transport Types</label>
          <div className="flex gap-2">
            <button
              onClick={selectAllModes}
              disabled={isLoading}
              className="text-small text-brand hover:text-primary/80 disabled:opacity-50 font-medium"
            >
              All
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {TRANSPORT_MODES.map(mode => {
            const isSelected =
              selectedTransportModes.length === 0 || selectedTransportModes.includes(mode.value)
            return (
              <button
                key={mode.value}
                onClick={() => toggleTransportMode(mode.value)}
                disabled={isLoading}
                className={`btn-bvv relative ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                aria-label={`Toggle ${mode.label}`}
                aria-pressed={isSelected}
              >
                <div className={isSelected ? '' : 'opacity-40 hover:opacity-60 transition-opacity'}>
                  <TransportBadge type={mode.value} />
                </div>
                {isSelected && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-status-healthy" />
                )}
              </button>
            )
          })}
        </div>
        {selectedTransportModes.length === 0 && (
          <p className="text-small text-muted italic">Showing all transport types</p>
        )}
      </div>
    </div>
  )
}
