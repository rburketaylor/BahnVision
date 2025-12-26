/**
 * Heatmap Stats Component
 * Displays summary statistics for cancellation and delay data
 */

import type { HeatmapSummary, HeatmapMetric } from '../../types/heatmap'

interface HeatmapStatsProps {
  summary: HeatmapSummary | null
  metric: HeatmapMetric
  isLoading?: boolean
}

export function HeatmapStats({ summary, metric, isLoading = false }: HeatmapStatsProps) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border p-4 animate-pulse">
        <h3 className="text-sm font-semibold text-foreground mb-3">Statistics</h3>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-6 bg-muted rounded" />
          ))}
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">Statistics</h3>
        <p className="text-sm text-muted-foreground">No data available</p>
      </div>
    )
  }

  const formatPercent = (rate: number) => `${(rate * 100).toFixed(1)}%`
  const formatNumber = (num: number) => num.toLocaleString()

  // Calculate selected overall rate based on metric
  const overallRate =
    metric === 'delays' ? (summary.overall_delay_rate ?? 0) : summary.overall_cancellation_rate

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <h3 className="text-sm font-semibold text-foreground mb-3">Statistics</h3>

      <div className="space-y-3">
        {/* Overall rate - highlighted based on selected metric */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Overall Rate</span>
          <span
            className={`text-sm font-medium ${
              overallRate > (metric === 'delays' ? 0.2 : 0.05)
                ? 'text-red-500'
                : overallRate > (metric === 'delays' ? 0.1 : 0.02)
                  ? 'text-yellow-500'
                  : 'text-green-500'
            }`}
          >
            {formatPercent(overallRate)}
            <span className="text-xs text-muted-foreground ml-1">
              ({metric === 'delays' ? 'delays' : 'cancellations'})
            </span>
          </span>
        </div>

        {/* Total departures */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Total Departures</span>
          <span className="text-sm font-medium text-foreground">
            {formatNumber(summary.total_departures)}
          </span>
        </div>

        {/* Cancellations count */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Cancellations</span>
          <span className="text-sm font-medium text-red-500">
            {formatNumber(summary.total_cancellations)}
          </span>
        </div>

        {/* Delays count */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Delays</span>
          <span className="text-sm font-medium text-orange-500">
            {formatNumber(summary.total_delays ?? 0)}
          </span>
        </div>

        {/* Stations monitored */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Stations</span>
          <span className="text-sm font-medium text-foreground">
            {formatNumber(summary.total_stations)}
          </span>
        </div>

        {/* Divider */}
        <div className="border-t border-border my-2" />

        {/* Most affected station */}
        {summary.most_affected_station && (
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Most Affected Station</span>
            <p className="text-sm font-medium text-foreground truncate">
              {summary.most_affected_station}
            </p>
          </div>
        )}

        {/* Most affected line */}
        {summary.most_affected_line && (
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Most Affected Line</span>
            <p className="text-sm font-medium text-foreground">{summary.most_affected_line}</p>
          </div>
        )}
      </div>
    </div>
  )
}
