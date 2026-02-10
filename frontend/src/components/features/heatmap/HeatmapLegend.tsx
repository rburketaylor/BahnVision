/**
 * Heatmap Legend Component
 * Displays color intensity legend for cancellation/delay impact.
 */

import { useState } from 'react'
import type { HeatmapEnabledMetrics } from '../../../types/heatmap'
import { DARK_HEATMAP_CONFIG, LIGHT_HEATMAP_CONFIG } from '../../../types/heatmap'
import { useTheme } from '../../../contexts/ThemeContext'

interface HeatmapLegendProps {
  className?: string
  enabledMetrics: HeatmapEnabledMetrics
}

interface LegendItem {
  color: string
  label: string
  value: string
}

export function HeatmapLegend({ className = '', enabledMetrics }: HeatmapLegendProps) {
  const { resolvedTheme } = useTheme()
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  const config = resolvedTheme === 'dark' ? DARK_HEATMAP_CONFIG : LIGHT_HEATMAP_CONFIG
  const stops = Object.entries(config.gradient)
    .map(([k, v]) => [Number(k), v] as const)
    .filter(([k]) => !Number.isNaN(k))
    .sort((a, b) => a[0] - b[0])

  const gradientCss = `linear-gradient(to right, ${stops
    .map(([k, v]) => `${v} ${Math.round(k * 100)}%`)
    .join(', ')})`

  const getLegendItems = (): LegendItem[] => {
    const swatches =
      resolvedTheme === 'dark'
        ? ['#2dd4bf', '#0ea5e9', '#f59e0b', '#ef4444']
        : ['#67e8f9', '#38bdf8', '#f59e0b', '#dc2626']

    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      return [
        { color: swatches[0], label: 'Low impact', value: '0-5%' },
        { color: swatches[1], label: 'Moderate impact', value: '5-15%' },
        { color: swatches[2], label: 'High impact', value: '15-25%' },
        { color: swatches[3], label: 'Severe', value: '>25%' },
      ]
    }
    if (enabledMetrics.delays) {
      return [
        { color: swatches[0], label: 'Low', value: '0-5%' },
        { color: swatches[1], label: 'Medium', value: '5-10%' },
        { color: swatches[2], label: 'High', value: '10-20%' },
        { color: swatches[3], label: 'Severe', value: '>20%' },
      ]
    }
    return [
      { color: swatches[0], label: 'Low', value: '0-2%' },
      { color: swatches[1], label: 'Medium', value: '2-5%' },
      { color: swatches[2], label: 'High', value: '5-10%' },
      { color: swatches[3], label: 'Severe', value: '>10%' },
    ]
  }

  const legendItems = getLegendItems()

  const getTitle = () => {
    if (enabledMetrics.cancellations && enabledMetrics.delays) {
      return 'Combined Intensity'
    }
    if (enabledMetrics.delays) {
      return 'Delay Intensity'
    }
    return 'Cancellation Intensity'
  }

  return (
    <div className={`rounded-md border border-border bg-card p-4 ${className}`}>
      <h3 className="mb-3 text-h3 text-foreground">{getTitle()}</h3>

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
}
