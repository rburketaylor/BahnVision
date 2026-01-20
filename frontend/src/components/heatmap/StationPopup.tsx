import type { StationStats } from '../../types/gtfs'
import type { HeatmapPointLight } from '../../types/heatmap'

interface StationPopupProps {
  station: HeatmapPointLight
  details?: StationStats
  isLoading: boolean
}

export function StationPopup({ station, details, isLoading }: StationPopupProps) {
  if (isLoading) {
    return (
      <div className="p-3">
        <h3 className="font-semibold text-base">{station.n}</h3>
        <div className="mt-2 flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
          <span className="text-sm text-muted-foreground">Loading...</span>
        </div>
        <div className="mt-3 pt-3 border-t border-border">
          <a
            href={`/station/${station.id}`}
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            Details →
          </a>
        </div>
      </div>
    )
  }

  if (!details) {
    return (
      <div className="p-3">
        <h3 className="font-semibold text-base">{station.n}</h3>
        <p className="text-sm text-muted-foreground mt-1">No data available</p>
        <div className="mt-3 pt-3 border-t border-border">
          <a
            href={`/station/${station.id}`}
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            Details →
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="p-3 min-w-[200px]">
      <h3 className="font-semibold text-base">{details.station_name}</h3>

      <div className="mt-3 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Departures</span>
          <span className="font-medium">{details.total_departures.toLocaleString()}</span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Cancellations</span>
          <span className="font-medium text-red-500">
            {details.cancelled_count} ({(details.cancellation_rate * 100).toFixed(1)}%)
          </span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Delays (&gt;5 min)</span>
          <span className="font-medium text-orange-500">
            {details.delayed_count} ({(details.delay_rate * 100).toFixed(1)}%)
          </span>
        </div>
      </div>

      {details.by_transport.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-xs text-muted-foreground mb-2">By Transport Type</p>
          {details.by_transport.map(t => (
            <div key={t.transport_type} className="flex justify-between text-xs">
              <span>{t.display_name}</span>
              <span>{((t.cancellation_rate + t.delay_rate) * 100).toFixed(1)}% issues</span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-border">
        <a
          href={`/station/${station.id}`}
          className="text-sm text-primary hover:underline flex items-center gap-1"
        >
          Details →
        </a>
      </div>
    </div>
  )
}
