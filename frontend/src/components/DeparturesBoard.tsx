import React from 'react'
import type { Departure } from '../types/api'

interface DeparturesBoardProps {
  departures: Departure[]
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

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-card sticky top-0 z-10">
          <tr>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
            >
              Line
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
            >
              Destination
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
            >
              Platform
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
            >
              Departure
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
            >
              Delay
            </th>
          </tr>
        </thead>
        <tbody className="bg-card divide-y divide-border">
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
              <React.Fragment key={hourKey}>
                {/* Hour header row */}
                <tr className="bg-gray-800/50">
                  <td colSpan={5} className="px-6 py-2 text-sm font-semibold text-gray-300">
                    {headerLabel}
                  </td>
                </tr>
                {/* Departures for this hour */}
                {hourDepartures.map((departure, index) => (
                  <tr
                    key={`${hourKey}-${index}`}
                    className={departure.cancelled ? 'bg-red-900/50' : 'hover:bg-gray-800/30'}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <span
                          className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-input text-gray-300`}
                        >
                          {departure.line}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">{departure.destination}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">{departure.platform}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">
                        {departure.realtime_time ? (
                          <>
                            <span className="font-semibold">{new Date(departure.realtime_time).toLocaleTimeString()}</span>
                            {departure.planned_time && (
                              <span className="text-xs text-gray-500 ml-2 line-through">
                                {new Date(departure.planned_time).toLocaleTimeString()}
                              </span>
                            )}
                          </>
                        ) : (
                          <span>{departure.planned_time ? new Date(departure.planned_time).toLocaleTimeString() : 'N/A'}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          departure.delay_minutes > 0 ? 'bg-red-900/50 text-red-300' : 'bg-green-900/50 text-green-300'
                        }`}
                      >
                        {departure.delay_minutes > 0 ? `+${departure.delay_minutes}` : 'On time'}
                      </span>
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
      {sortedDepartures.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No departures found for the selected time and filters.
        </div>
      )}
    </div>
  )
}
