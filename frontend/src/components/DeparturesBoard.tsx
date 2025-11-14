import type { Departure } from '../types/api'

interface DeparturesBoardProps {
  departures: Departure[]
}

// Transport type color mapping
const getTransportTypeColor = (transportType?: string) => {
  switch (transportType) {
    case 'UBAHN':
      return 'bg-ubahn text-white'
    case 'SBAHN':
      return 'bg-sbahn text-white'
    case 'TRAM':
      return 'bg-tram text-white'
    case 'BUS':
    case 'REGIONAL_BUS':
      return 'bg-bus text-white'
    case 'BAHN':
      return 'bg-gray-700 text-white'
    default:
      return 'bg-gray-600 text-white'
  }
}

// Format time for display
const formatTime = (dateString: string | null | undefined) => {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function DeparturesBoard({ departures }: DeparturesBoardProps) {
  // Sort departures by effective departure time (realtime if available, otherwise planned)
  const sortedDepartures = [...departures].sort((a, b) => {
    const timeA = a.realtime_time || a.planned_time
    const timeB = b.realtime_time || b.planned_time
    if (!timeA) return 1
    if (!timeB) return -1
    return new Date(timeA).getTime() - new Date(timeB).getTime()
  })

  // Group departures by hour
  const groupedDepartures = sortedDepartures.reduce<Record<string, Departure[]>>((groups, departure) => {
    const effectiveTime = departure.realtime_time || departure.planned_time
    if (!effectiveTime) return groups

    const date = new Date(effectiveTime)
    const pad = (value: number) => value.toString().padStart(2, '0')
    const hourKey = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}-${pad(date.getHours())}`

    if (!groups[hourKey]) {
      groups[hourKey] = []
    }
    groups[hourKey].push(departure)
    return groups
  }, {})

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
    <div className="space-y-6">
      {Object.entries(groupedDepartures).map(([hourKey, hourDepartures]) => {
        const headerDeparture = hourDepartures[0]
        const headerTime = headerDeparture?.realtime_time || headerDeparture?.planned_time
        const headerLabel = headerTime
          ? new Date(headerTime).toLocaleString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
              day: '2-digit',
              month: 'short',
            })
          : hourKey

        return (
          <div key={hourKey} className="space-y-4">
            {/* Time header */}
            <div className="sticky top-20 z-10 bg-background/95 backdrop-blur-sm border-b border-border pb-2">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <span className="w-2 h-2 bg-primary rounded-full"></span>
                {headerLabel}
              </h3>
            </div>

            {/* Departure cards */}
            <div className="grid gap-3 sm:gap-4">
              {hourDepartures.map((departure, index) => (
                <div
                  key={`${hourKey}-${index}`}
                  className={`
                    relative rounded-lg border transition-all duration-200 hover:shadow-md
                    ${departure.cancelled
                      ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                      : 'bg-card border-border hover:border-primary/50'
                    }
                  `}
                >
                  <div className="p-4 sm:p-5">
                    {/* Header with line and time */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="flex flex-col items-center">
                          <span className={`
                            px-3 py-1 rounded-md text-xs font-bold text-center min-w-[3rem]
                            ${getTransportTypeColor(departure.transport_type)}
                          `}>
                            {departure.line}
                          </span>
                          {departure.transport_type && (
                            <span className="text-xs text-gray-500 mt-1">
                              {departure.transport_type === 'REGIONAL_BUS' ? 'BUS' : departure.transport_type}
                            </span>
                          )}
                        </div>

                        <div className="flex-1">
                          <div className="font-semibold text-foreground text-lg">
                            {departure.destination}
                          </div>
                          {departure.platform && (
                            <div className="text-sm text-gray-500 mt-1">
                              Platform {departure.platform}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Departure time and status */}
                      <div className="text-right">
                        <div className="text-2xl font-bold text-foreground">
                          {formatTime(departure.realtime_time || departure.planned_time)}
                        </div>

                        {/* Delay indicator */}
                        {departure.delay_minutes !== undefined && (
                          <div className="mt-1">
                            {departure.cancelled ? (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                                ❌ Cancelled
                              </span>
                            ) : departure.delay_minutes > 0 ? (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                                ⚠️ +{departure.delay_minutes} min
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                                ✅ On time
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Time comparison for delayed trains */}
                    {departure.realtime_time && departure.planned_time &&
                     new Date(departure.realtime_time).getTime() !== new Date(departure.planned_time).getTime() && (
                      <div className="text-xs text-gray-500 border-t border-border pt-2 mt-2">
                        <div className="flex items-center gap-2">
                          <span>Scheduled: {formatTime(departure.planned_time)}</span>
                          <span>→</span>
                          <span>Actual: {formatTime(departure.realtime_time)}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
