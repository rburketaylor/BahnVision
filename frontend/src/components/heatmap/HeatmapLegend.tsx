/**
 * Heatmap Legend Component
 * Displays the color legend for cancellation/delay intensity
 * BVV-styled with gradient bar and improved visual hierarchy
 */

import { useState } from 'react'
import type { HeatmapEnabledMetrics } from '../../types/heatmap'
import { DARK_HEATMAP_CONFIG, LIGHT_HEATMAP_CONFIG } from '../../types/heatmap'
import { useTheme } from '../../contexts/ThemeContext'

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

  // Determine legend items based on enabled metrics
  const getLegendItems = (): LegendItem[] => {
    const swatches =
      resolvedTheme === 'dark'
        ? [
            'rgba(255, 168, 0, 0.70)',
            'rgba(255, 98, 0, 0.80)',
            'rgba(255, 20, 60, 0.90)',
            'rgba(190, 0, 60, 1.0)',
          ]
        : [
            'rgba(34, 211, 238, 0.55)',
            'rgba(59, 130, 246, 0.70)',
            'rgba(99, 102, 241, 0.82)',
            'rgba(139, 92, 246, 0.95)',
          ]

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

  // Determine legend title based on enabled metrics
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
    <div className={`bg-card rounded-lg border border-border p-4 ${className}`}>
      <h3 className="text-h3 text-foreground mb-3">{getTitle()}</h3>

      {/* Gradient bar with tick marks */}
      <div className="relative mb-2">
        <div
          className="h-5 w-full rounded-md shadow-inner"
          style={{
            background: gradientCss,
          }}
        />
        {/* Tick marks */}
        <div className="absolute top-0 left-0 w-full flex justify-between px-1 -mt-1">
          <div className="w-px h-6 bg-border/50" />
          <div className="w-px h-6 bg-border/50" />
          <div className="w-px h-6 bg-border/50" />
          <div className="w-px h-6 bg-border/50" />
        </div>
      </div>

      <div className="flex justify-between mb-4">
        <span className="text-tiny text-muted">Low</span>
        <span className="text-tiny text-muted">Medium</span>
        <span className="text-tiny text-muted">High</span>
      </div>

      {/* Interactive legend items */}
      <div className="space-y-2 stagger-animation">
        {legendItems.map((item, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 py-1.5 px-2 rounded-md transition-all cursor-default ${
              hoveredIndex === index ? 'bg-muted/50 -translate-x-1' : ''
            }`}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <div
              className="w-4 h-4 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: item.color }}
            />
            <div className="flex-1 min-w-0">
              <span className="text-body text-muted block">{item.label}</span>
            </div>
            <span className="text-small font-medium text-foreground tabular-nums">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
