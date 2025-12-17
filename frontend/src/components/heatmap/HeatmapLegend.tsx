/**
 * Heatmap Legend Component
 * Displays the color legend for cancellation/delay intensity
 */

import type { HeatmapMetric } from '../../types/heatmap'
import { DARK_HEATMAP_CONFIG, LIGHT_HEATMAP_CONFIG } from '../../types/heatmap'
import { useTheme } from '../../contexts/ThemeContext'

interface HeatmapLegendProps {
  className?: string
  metric: HeatmapMetric
}

export function HeatmapLegend({ className = '', metric }: HeatmapLegendProps) {
  const { resolvedTheme } = useTheme()

  const config = resolvedTheme === 'dark' ? DARK_HEATMAP_CONFIG : LIGHT_HEATMAP_CONFIG
  const stops = Object.entries(config.gradient)
    .map(([k, v]) => [Number(k), v] as const)
    .filter(([k]) => !Number.isNaN(k))
    .sort((a, b) => a[0] - b[0])

  const gradientCss = `linear-gradient(to right, ${stops
    .map(([k, v]) => `${v} ${Math.round(k * 100)}%`)
    .join(', ')})`

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

  return (
    <div className={`bg-card rounded-lg border border-border p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-foreground mb-3">
        {metric === 'delays' ? 'Delay Intensity' : 'Cancellation Intensity'}
      </h3>

      <div className="flex items-center gap-2">
        {/* Gradient bar */}
        <div
          className="h-4 flex-1 rounded"
          style={{
            background: gradientCss,
          }}
        />
      </div>

      <div className="flex justify-between mt-1">
        <span className="text-xs text-muted-foreground">Low</span>
        <span className="text-xs text-muted-foreground">Medium</span>
        <span className="text-xs text-muted-foreground">High</span>
      </div>

      {/* Legend items */}
      <div className="mt-4 space-y-2 text-xs">
        {metric === 'delays' ? (
          <>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[0] }} />
              <span className="text-muted-foreground">0-5% delays</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[1] }} />
              <span className="text-muted-foreground">5-10% delays</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[2] }} />
              <span className="text-muted-foreground">10-20% delays</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[3] }} />
              <span className="text-muted-foreground">{'>'}20% delays</span>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[0] }} />
              <span className="text-muted-foreground">0-2% cancellations</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[1] }} />
              <span className="text-muted-foreground">2-5% cancellations</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[2] }} />
              <span className="text-muted-foreground">5-10% cancellations</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: swatches[3] }} />
              <span className="text-muted-foreground">{'>'}10% cancellations</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
