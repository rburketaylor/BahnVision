/**
 * Heatmap Legend Component
 * Displays the color legend for cancellation intensity
 */

interface HeatmapLegendProps {
  className?: string
}

export function HeatmapLegend({ className = '' }: HeatmapLegendProps) {
  return (
    <div className={`bg-card rounded-lg border border-border p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-foreground mb-3">Cancellation Intensity</h3>

      <div className="flex items-center gap-2">
        {/* Gradient bar */}
        <div
          className="h-4 flex-1 rounded"
          style={{
            background:
              'linear-gradient(to right, rgba(0,255,0,0.6), rgba(255,255,0,0.7), rgba(255,165,0,0.8), rgba(255,0,0,1))',
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
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500/60" />
          <span className="text-muted-foreground">0-2% cancellations</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
          <span className="text-muted-foreground">2-5% cancellations</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-orange-500/80" />
          <span className="text-muted-foreground">5-10% cancellations</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-muted-foreground">&gt;10% cancellations</span>
        </div>
      </div>
    </div>
  )
}
