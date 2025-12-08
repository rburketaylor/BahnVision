import { useState, useMemo } from 'react'
import type { TransitDeparture } from '../types/gtfs'

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
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Time Format:</span>
      <div className="relative inline-flex h-7 w-[4.5rem] items-center rounded-md bg-gray-200 dark:bg-gray-600 transition-colors">
        <button
          onClick={() => onToggle(!use24Hour)}
          className="relative inline-flex h-7 w-[4.5rem] items-center rounded-md bg-transparent transition-colors"
        >
          <span
            className={`inline-block h-5 w-[2.25rem] transform rounded-sm bg-white shadow-md transition-transform flex items-center justify-center text-sm font-sans font-semibold ${
              use24Hour ? 'translate-x-1' : 'translate-x-8'
            }`}
          >
            {use24Hour ? '24' : '12'}
          </span>
        </button>
      </div>
    </div>
  )
}

// Format time for display
const formatTime = (dateString: string | null | undefined, use24Hour: boolean = true) => {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: !use24Hour,
  })
}

export function DeparturesBoard({
  departures,
  use24Hour: initialUse24Hour = true,
}: DeparturesBoardProps) {
  const [use24Hour, setUse24Hour] = useState(initialUse24Hour)

  // Sort departures by effective departure time (realtime if available, otherwise scheduled)
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
      <div className="text-center py-12">
        <div className="text-6xl mb-4">🚦</div>
        <div className="text-gray-500 text-lg font-medium">No departures found</div>
        <div className="text-gray-400 text-sm mt-1">Try adjusting your filters or time range</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with time format toggle */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-foreground">
          {sortedDepartures.length} departure{sortedDepartures.length !== 1 ? 's' : ''}
        </h2>
        <TimeFormatToggle use24Hour={use24Hour} onToggle={setUse24Hour} />
      </div>

      {/* Departures list with better spacing */}
      <div className="space-y-3">
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
          // Map GTFS route types to display names
          const transportType = departure.route_short_name || 'Transit'

          return (
            <div key={index} className="group">
              <div
                className={`
                  flex items-center gap-4 px-4 py-4 rounded-xl transition-all duration-200 border
                  ${
                    isCancelled
                      ? 'bg-red-50/40 border-red-200 dark:bg-red-900/20 dark:border-red-800/60 hover:bg-red-50/60 dark:hover:bg-red-900/30'
                      : isDelayed
                        ? 'bg-yellow-50/40 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800/60 hover:bg-yellow-50/60 dark:hover:bg-yellow-900/30'
                        : 'bg-card border-border hover:border-primary/30 hover:shadow-sm'
                  }
                `}
              >
                {/* Transport line and type */}
                <div className="flex items-center gap-3 min-w-[5rem]">
                  <div
                    className={`
                    px-3 py-1.5 rounded-lg text-sm font-bold text-center min-w-[3rem]
                    bg-primary text-white
                  `}
                  >
                    {departure.route_short_name || '?'}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">
                    {transportType}
                  </div>
                </div>

                {/* Time */}
                <div className="text-xl font-mono font-semibold text-foreground min-w-[5rem]">
                  {time}
                </div>

                {/* Destination */}
                <div className="flex-1 text-base font-medium text-foreground">
                  {departure.headsign}
                </div>

                {/* Status info */}
                <div className="flex items-center gap-3">
                  {isCancelled ? (
                    <span className="px-3 py-1 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded-lg text-sm font-medium">
                      Cancelled
                    </span>
                  ) : isDelayed ? (
                    <span className="px-3 py-1 bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 rounded-lg text-sm font-medium">
                      +{delayMinutes}m delay
                    </span>
                  ) : (
                    <span className="px-3 py-1 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-lg text-sm font-medium">
                      On time
                    </span>
                  )}
                </div>
              </div>

              {/* Separator */}
              {index < sortedDepartures.length - 1 && (
                <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent my-4" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
