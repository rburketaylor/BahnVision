/**
 * Heatmap Stats Component
 * Displays summary statistics for cancellation and delay data
 * BVV-styled with metric cards, color-coded accents, and tabular numbers
 */

import type { HeatmapSummary, HeatmapEnabledMetrics } from '../../types/heatmap'

interface HeatmapStatsProps {
  summary: HeatmapSummary | null
  enabledMetrics: HeatmapEnabledMetrics
  isLoading?: boolean
}

export function HeatmapStats({ summary, enabledMetrics, isLoading = false }: HeatmapStatsProps) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-h3 text-foreground mb-3">Statistics</h3>
        <div className="space-y-3 stagger-animation">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-6 bg-muted rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-h3 text-foreground mb-3">Statistics</h3>
        <p className="text-body text-muted">No data available</p>
      </div>
    )
  }

  const formatPercent = (rate: number) => `${(rate * 100).toFixed(1)}%`
  const formatNumber = (num: number) => num.toLocaleString()

  // Calculate overall rate based on enabled metrics
  const getOverallRateInfo = () => {
    const cancellationRate = summary.overall_cancellation_rate
    const delayRate = summary.overall_delay_rate ?? 0

    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      // Combined rate
      const combinedRate = cancellationRate + delayRate
      return {
        rate: combinedRate,
        label: 'combined',
        accent: 'red' as const,
        highThreshold: 0.25,
        mediumThreshold: 0.12,
      }
    }
    if (enabledMetrics.delays) {
      return {
        rate: delayRate,
        label: 'delays',
        accent: 'orange' as const,
        highThreshold: 0.2,
        mediumThreshold: 0.1,
      }
    }
    return {
      rate: cancellationRate,
      label: 'cancellations',
      accent: 'red' as const,
      highThreshold: 0.05,
      mediumThreshold: 0.02,
    }
  }

  const rateInfo = getOverallRateInfo()

  // Determine accent color based on rate
  const getRateAccent = (rate: number) => {
    if (rate > rateInfo.highThreshold) return 'red'
    if (rate > rateInfo.mediumThreshold) return 'orange'
    return 'green'
  }

  const rateAccent = getRateAccent(rateInfo.rate)
  const accentColors = {
    red: 'text-status-critical',
    orange: 'text-status-warning',
    green: 'text-status-healthy',
  }
  const cardAccentClass = `card-accent-${rateAccent}`

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <h3 className="text-h3 text-foreground mb-3">Statistics</h3>

      <div className="space-y-3 stagger-animation">
        {/* Overall rate - highlighted metric card */}
        <div className={`card-base ${cardAccentClass} p-3 -ml-1`}>
          <div className="flex justify-between items-center">
            <span className="text-body text-muted">Overall Rate</span>
            <span className={`text-h2 tabular-nums ${accentColors[rateAccent]}`}>
              {formatPercent(rateInfo.rate)}
            </span>
          </div>
          <span className="text-tiny text-muted">{rateInfo.label}</span>
        </div>

        {/* Total departures */}
        <div className="flex justify-between items-center py-2 border-b border-border/60">
          <span className="text-body text-muted">Total Departures</span>
          <span className="text-body font-medium text-foreground tabular-nums">
            {formatNumber(summary.total_departures)}
          </span>
        </div>

        {/* Cancellations count */}
        <div className="flex justify-between items-center py-2 border-b border-border/60">
          <span className="text-body text-muted">Cancellations</span>
          <span className="text-body font-medium text-status-critical tabular-nums">
            {formatNumber(summary.total_cancellations)}
          </span>
        </div>

        {/* Delays count */}
        <div className="flex justify-between items-center py-2 border-b border-border/60">
          <span className="text-body text-muted">Delays</span>
          <span className="text-body font-medium text-status-warning tabular-nums">
            {formatNumber(summary.total_delays ?? 0)}
          </span>
        </div>

        {/* Stations monitored */}
        <div className="flex justify-between items-center py-2 border-b border-border/60">
          <span className="text-body text-muted">Stations</span>
          <span className="text-body font-medium text-foreground tabular-nums">
            {formatNumber(summary.total_stations)}
          </span>
        </div>

        {/* Divider */}
        <div className="border-t border-border my-2" />

        {/* Most affected station */}
        {summary.most_affected_station && (
          <div className="space-y-1">
            <span className="text-small text-muted">Most Affected Station</span>
            <p className="text-body font-medium text-foreground truncate">
              {summary.most_affected_station}
            </p>
          </div>
        )}

        {/* Most affected line */}
        {summary.most_affected_line && (
          <div className="space-y-1">
            <span className="text-small text-muted">Most Affected Line</span>
            <p className="text-body font-medium text-foreground">{summary.most_affected_line}</p>
          </div>
        )}
      </div>
    </div>
  )
}
