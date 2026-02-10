/**
 * Heatmap Stats Component
 * Displays summary statistics for cancellation and delay data
 */

import { AlertTriangle, BarChart3 } from 'lucide-react'
import type { HeatmapSummary, HeatmapEnabledMetrics } from '../../../types/heatmap'

interface HeatmapStatsProps {
  summary: HeatmapSummary | null
  enabledMetrics: HeatmapEnabledMetrics
  isLoading?: boolean
}

export function HeatmapStats({ summary, enabledMetrics, isLoading = false }: HeatmapStatsProps) {
  if (isLoading) {
    return (
      <div className="rounded-md border border-border bg-card p-4">
        <h3 className="mb-3 text-h3 text-foreground">Statistics</h3>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-5 animate-pulse rounded bg-surface-muted" />
          ))}
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="rounded-md border border-border bg-card p-4">
        <h3 className="mb-3 text-h3 text-foreground">Statistics</h3>
        <p className="text-body text-muted-foreground">No data available</p>
      </div>
    )
  }

  const formatPercent = (rate: number) => `${(rate * 100).toFixed(1)}%`
  const formatNumber = (num: number) => num.toLocaleString()

  const getOverallRateInfo = () => {
    const cancellationRate = summary.overall_cancellation_rate
    const delayRate = summary.overall_delay_rate ?? 0

    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      const combinedRate = cancellationRate + delayRate
      return {
        rate: combinedRate,
        label: 'combined',
        highThreshold: 0.25,
        mediumThreshold: 0.12,
      }
    }
    if (enabledMetrics.delays) {
      return {
        rate: delayRate,
        label: 'delays',
        highThreshold: 0.2,
        mediumThreshold: 0.1,
      }
    }
    return {
      rate: cancellationRate,
      label: 'cancellations',
      highThreshold: 0.05,
      mediumThreshold: 0.02,
    }
  }

  const rateInfo = getOverallRateInfo()

  const getRateAccent = (rate: number) => {
    if (rate > rateInfo.highThreshold) return 'text-status-critical'
    if (rate > rateInfo.mediumThreshold) return 'text-status-warning'
    return 'text-status-healthy'
  }

  return (
    <div className="rounded-md border border-border bg-card p-4">
      <h3 className="mb-3 text-h3 text-foreground">Statistics</h3>

      <div className="space-y-3">
        <div className="rounded-md border border-border bg-surface-elevated p-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 text-body text-muted-foreground">
              <BarChart3 className="h-4 w-4" />
              Overall Rate
            </span>
            <span className={`text-h2 tabular-nums ${getRateAccent(rateInfo.rate)}`}>
              {formatPercent(rateInfo.rate)}
            </span>
          </div>
          <span className="text-tiny text-muted-foreground">{rateInfo.label}</span>
        </div>

        <StatRow label="Total Departures" value={formatNumber(summary.total_departures)} />
        <StatRow
          label="Cancellations"
          value={formatNumber(summary.total_cancellations)}
          accent="text-status-critical"
        />
        <StatRow
          label="Delays"
          value={formatNumber(summary.total_delays ?? 0)}
          accent="text-status-warning"
        />
        <StatRow label="Stations" value={formatNumber(summary.total_stations)} />

        {summary.most_affected_station && (
          <div className="space-y-1 border-t border-border pt-2">
            <span className="text-small text-muted-foreground">Most Affected Station</span>
            <p className="truncate text-body font-semibold text-foreground">
              {summary.most_affected_station}
            </p>
          </div>
        )}

        {summary.most_affected_line && (
          <div className="space-y-1">
            <span className="text-small text-muted-foreground">Most Affected Line</span>
            <p className="text-body font-semibold text-foreground">{summary.most_affected_line}</p>
          </div>
        )}

        {rateInfo.rate > rateInfo.highThreshold && (
          <div className="inline-flex items-center gap-2 rounded-md border border-status-critical/30 bg-status-critical/10 px-2.5 py-1.5 text-small text-status-critical">
            <AlertTriangle className="h-4 w-4" />
            Elevated disruption detected
          </div>
        )}
      </div>
    </div>
  )
}

function StatRow({
  label,
  value,
  accent = 'text-foreground',
}: {
  label: string
  value: string
  accent?: string
}) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-2 last:border-b-0">
      <span className="text-body text-muted-foreground">{label}</span>
      <span className={`text-body tabular-nums ${accent}`}>{value}</span>
    </div>
  )
}
