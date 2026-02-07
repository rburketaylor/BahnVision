import { useState, useMemo } from 'react'
import { Clock3, TrainFront } from 'lucide-react'
import type { TransitDeparture } from '../../../types/gtfs'
import { formatTime } from '../../../utils/time'

interface DeparturesBoardProps {
  departures: TransitDeparture[]
  use24Hour?: boolean
}

interface TimeFormatToggleProps {
  use24Hour: boolean
  onToggle: (use24Hour: boolean) => void
}

function TimeFormatToggle({ use24Hour, onToggle }: TimeFormatToggleProps) {
  return (
    <div className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-elevated p-1">
      <button
        type="button"
        className={`btn-bvv rounded-sm px-2.5 py-1 text-small font-semibold ${
          use24Hour ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'
        }`}
        onClick={() => onToggle(true)}
      >
        24
      </button>
      <button
        type="button"
        className={`btn-bvv rounded-sm px-2.5 py-1 text-small font-semibold ${
          !use24Hour ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'
        }`}
        onClick={() => onToggle(false)}
      >
        12
      </button>
    </div>
  )
}

export function DeparturesBoard({
  departures,
  use24Hour: initialUse24Hour = true,
}: DeparturesBoardProps) {
  const [use24Hour, setUse24Hour] = useState(initialUse24Hour)

  const sortedDepartures = useMemo(
    () =>
      [...departures].sort((a, b) => {
        const timeA = a.realtime_departure || a.scheduled_departure
        const timeB = b.realtime_departure || b.scheduled_departure
        if (!timeA) return 1
        if (!timeB) return -1
        return new Date(timeA).getTime() - new Date(timeB).getTime()
      }),
    [departures]
  )

  if (sortedDepartures.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-elevated p-8 text-center">
        <div className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-md border border-border bg-card text-muted-foreground">
          <TrainFront className="h-5 w-5" />
        </div>
        <div className="text-h3 text-foreground">No departures found</div>
        <div className="mt-1 text-small text-muted-foreground">
          Try adjusting your filters or time range
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-h2 text-foreground">
          {sortedDepartures.length} departure{sortedDepartures.length !== 1 ? 's' : ''}
        </h2>
        <div className="inline-flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-small text-muted-foreground">
            <Clock3 className="h-4 w-4" />
            Time format
          </span>
          <TimeFormatToggle use24Hour={use24Hour} onToggle={setUse24Hour} />
        </div>
      </div>

      <div className="space-y-2">
        {sortedDepartures.map((departure, index) => {
          const time = formatTime(
            departure.realtime_departure || departure.scheduled_departure,
            use24Hour
          )
          const delayMinutes = departure.departure_delay_seconds
            ? Math.round(departure.departure_delay_seconds / 60)
            : 0
          const isDelayed = delayMinutes > 0
          const isCancelled = departure.schedule_relationship === 'SKIPPED'
          const transportType = departure.route_short_name || 'Transit'

          return (
            <div
              key={index}
              className={`rounded-md border px-4 py-3 transition-colors ${
                isCancelled
                  ? 'border-red-500/35 bg-red-500/8'
                  : isDelayed
                    ? 'border-amber-500/35 bg-amber-500/8'
                    : 'border-border bg-card hover:border-primary/25'
              }`}
            >
              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex min-w-[4.25rem] items-center justify-center rounded-sm bg-primary px-2 py-1 text-small font-semibold text-primary-foreground">
                  {departure.route_short_name || '?'}
                </div>

                <div className="min-w-[4.5rem] text-h3 tabular-nums text-foreground">{time}</div>

                <div className="min-w-[9rem] flex-1 text-body font-semibold text-foreground">
                  {departure.headsign}
                </div>

                <div className="text-small text-muted-foreground">{transportType}</div>

                <div>
                  {isCancelled ? (
                    <span className="inline-flex rounded-sm border border-red-500/35 bg-red-500/12 px-2 py-1 text-small font-semibold text-red-600 dark:text-red-300">
                      Cancelled
                    </span>
                  ) : isDelayed ? (
                    <span className="inline-flex rounded-sm border border-amber-500/35 bg-amber-500/12 px-2 py-1 text-small font-semibold text-amber-700 dark:text-amber-300">
                      +{delayMinutes}m delay
                    </span>
                  ) : (
                    <span className="inline-flex rounded-sm border border-emerald-500/35 bg-emerald-500/12 px-2 py-1 text-small font-semibold text-emerald-700 dark:text-emerald-300">
                      On time
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
