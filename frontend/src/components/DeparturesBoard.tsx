import type { Departure } from '../types/api'

interface DeparturesBoardProps {
  departures: Departure[]
}

export function DeparturesBoard({ departures }: DeparturesBoardProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-card">
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
          {departures.map((departure, index) => (
            <tr key={index} className={departure.cancelled ? 'bg-red-900/50' : ''}>
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
        </tbody>
      </table>
    </div>
  )
}
