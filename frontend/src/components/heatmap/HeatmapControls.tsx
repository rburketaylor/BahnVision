/**
 * Heatmap Controls Component
 * Time range selector and transport mode filters for the heatmap
 */

import type { TransportType } from '../../types/api'
import type { TimeRangePreset, HeatmapEnabledMetrics } from '../../types/heatmap'
import { TIME_RANGE_LABELS, HEATMAP_METRIC_LABELS } from '../../types/heatmap'

interface HeatmapControlsProps {
  timeRange: TimeRangePreset
  onTimeRangeChange: (range: TimeRangePreset) => void
  selectedTransportModes: TransportType[]
  onTransportModesChange: (modes: TransportType[]) => void
  enabledMetrics: HeatmapEnabledMetrics
  onEnabledMetricsChange: (metrics: HeatmapEnabledMetrics) => void
  isLoading?: boolean
}

const TRANSPORT_MODES: { value: TransportType; label: string; color: string }[] = [
  { value: 'UBAHN', label: 'U-Bahn', color: 'bg-blue-600' },
  { value: 'SBAHN', label: 'S-Bahn', color: 'bg-green-600' },
  { value: 'TRAM', label: 'Tram', color: 'bg-red-500' },
  { value: 'BUS', label: 'Bus', color: 'bg-purple-600' },
  { value: 'BAHN', label: 'Regional', color: 'bg-gray-600' },
]

const TIME_RANGES: TimeRangePreset[] = ['1h', '6h', '24h', '7d', '30d']

export function HeatmapControls({
  timeRange,
  onTimeRangeChange,
  selectedTransportModes,
  onTransportModesChange,
  enabledMetrics,
  onEnabledMetricsChange,
  isLoading = false,
}: HeatmapControlsProps) {
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

  const clearAllModes = () => {
    onTransportModesChange([])
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
      <h3 className="text-sm font-semibold text-foreground">Filters</h3>

      {/* Time Range Selection */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">Time Range</label>
        <div className="flex flex-wrap gap-2">
          {TIME_RANGES.map(range => (
            <button
              key={range}
              onClick={() => onTimeRangeChange(range)}
              disabled={isLoading}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                timeRange === range
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {TIME_RANGE_LABELS[range]}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Toggles */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">Show Metrics</label>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => toggleMetric('cancellations')}
            disabled={isLoading}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              enabledMetrics.cancellations
                ? 'bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/40'
                : 'bg-muted text-muted-foreground hover:bg-muted/80 border border-transparent'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            aria-pressed={enabledMetrics.cancellations}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                enabledMetrics.cancellations ? 'bg-red-500' : 'bg-muted-foreground/30'
              }`}
            />
            {HEATMAP_METRIC_LABELS.cancellations}
          </button>
          <button
            onClick={() => toggleMetric('delays')}
            disabled={isLoading}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              enabledMetrics.delays
                ? 'bg-orange-500/20 text-orange-600 dark:text-orange-400 border border-orange-500/40'
                : 'bg-muted text-muted-foreground hover:bg-muted/80 border border-transparent'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            aria-pressed={enabledMetrics.delays}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                enabledMetrics.delays ? 'bg-orange-500' : 'bg-muted-foreground/30'
              }`}
            />
            {HEATMAP_METRIC_LABELS.delays}
          </button>
        </div>
        {enabledMetrics.cancellations && enabledMetrics.delays && (
          <p className="text-xs text-muted-foreground italic">
            Showing combined cancellation & delay intensity
          </p>
        )}
      </div>

      {/* Transport Mode Filters */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-muted-foreground">Transport Types</label>
          <div className="flex gap-2">
            <button
              onClick={selectAllModes}
              disabled={isLoading}
              className="text-xs text-primary hover:text-primary/80 disabled:opacity-50"
            >
              All
            </button>
            <span className="text-muted-foreground">|</span>
            <button
              onClick={clearAllModes}
              disabled={isLoading}
              className="text-xs text-primary hover:text-primary/80 disabled:opacity-50"
            >
              None
            </button>
          </div>
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
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isSelected
                    ? `${mode.color} text-white`
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {mode.label}
              </button>
            )
          })}
        </div>
        {selectedTransportModes.length === 0 && (
          <p className="text-xs text-muted-foreground italic">Showing all transport types</p>
        )}
      </div>
    </div>
  )
}
