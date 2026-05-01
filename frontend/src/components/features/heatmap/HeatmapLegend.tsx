/**
 * Heatmap Legend Component
 * Displays color intensity legend for cancellation/delay impact.
 */

import { memo, useMemo, useState } from 'react'
import type { HeatmapEnabledMetrics } from '../../../types/heatmap'
import { BVV_POINT_COLOR_STOPS, getBVVMarkerColor } from './markerStyles'

interface HeatmapLegendProps {
  className?: string
  enabledMetrics: HeatmapEnabledMetrics
}

interface LegendItem {
  color: string
  intensity: number
  label: string
  value: string
}

export const HeatmapLegend = memo(function HeatmapLegend({
  className = '',
  enabledMetrics,
}: HeatmapLegendProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  const gradientCss = useMemo(
    () =>
      `linear-gradient(to right, ${BVV_POINT_COLOR_STOPS.map(
        ({ intensity, color }) => `${color} ${Math.round(intensity * 100)}%`
      ).join(', ')})`,
    []
  )

  const legendItems = useMemo<LegendItem[]>(() => {
    let metricItems: Array<Omit<LegendItem, 'color'>>

    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      metricItems = [
        { intensity: 0.1, label: 'Low impact', value: '0-5%' },
        { intensity: 0.4, label: 'Moderate impact', value: '5-15%' },
        { intensity: 0.7, label: 'High impact', value: '15-25%' },
        { intensity: 0.9, label: 'Severe', value: '>25%' },
      ]
    } else if (enabledMetrics.delays) {
      metricItems = [
        { intensity: 0.125, label: 'Low', value: '0-5%' },
        { intensity: 0.375, label: 'Medium', value: '5-10%' },
        { intensity: 0.75, label: 'High', value: '10-20%' },
        { intensity: 0.95, label: 'Severe', value: '>20%' },
      ]
    } else {
      metricItems = [
        { intensity: 0.1, label: 'Low', value: '0-2%' },
        { intensity: 0.35, label: 'Medium', value: '2-5%' },
        { intensity: 0.75, label: 'High', value: '5-10%' },
        { intensity: 0.95, label: 'Severe', value: '>10%' },
      ]
    }

    return metricItems.map(item => ({
      ...item,
      color: getBVVMarkerColor(item.intensity),
    }))
  }, [enabledMetrics.cancellations, enabledMetrics.delays])

  const title = useMemo(() => {
    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      return 'Combined Intensity'
    }
    if (enabledMetrics.delays) {
      return 'Delay Intensity'
    }
    return 'Cancellation Intensity'
  }, [enabledMetrics.cancellations, enabledMetrics.delays])

  return (
    <div className={`rounded-md border border-border bg-card p-4 ${className}`}>
      <h3 className="mb-3 text-h3 text-foreground">{title}</h3>

      <div className="relative mb-2">
        <div className="h-4 w-full rounded-sm shadow-inner" style={{ background: gradientCss }} />
        <div className="absolute -top-1 left-0 flex w-full justify-between px-1">
          <div className="h-6 w-px bg-border/70" />
          <div className="h-6 w-px bg-border/70" />
          <div className="h-6 w-px bg-border/70" />
          <div className="h-6 w-px bg-border/70" />
        </div>
      </div>

      <div className="mb-4 flex justify-between">
        <span className="text-tiny text-muted-foreground">Low</span>
        <span className="text-tiny text-muted-foreground">Medium</span>
        <span className="text-tiny text-muted-foreground">High</span>
      </div>

      <div className="space-y-2 stagger-enter">
        {legendItems.map((item, index) => (
          <div
            key={index}
            className={`flex cursor-default items-center gap-3 rounded-sm px-2 py-1.5 transition-all ${
              hoveredIndex === index ? 'bg-surface-elevated' : ''
            }`}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <div
              className="h-3.5 w-3.5 shrink-0 rounded-sm"
              style={{ backgroundColor: item.color }}
            />
            <div className="min-w-0 flex-1">
              <span className="block text-body text-muted-foreground">{item.label}</span>
            </div>
            <span className="text-small tabular-nums text-foreground">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
})
