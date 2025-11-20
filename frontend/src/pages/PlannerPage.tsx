/**
 * Route Planner Page
 * Plan journeys between two stations
 */

import { useState } from 'react'
import { useRoutePlanner } from '../hooks/useRoutePlanner'
import { StationSearchEnhanced } from '../components/StationSearchEnhanced'
import type { Station, TransportType, RoutePlanParams } from '../types/api'

const ALL_TRANSPORT_TYPES: TransportType[] = [
  'BAHN',
  'SBAHN',
  'UBAHN',
  'TRAM',
  'BUS',
  'REGIONAL_BUS',
  'SCHIFF',
]

const toDateTimeLocalValue = (isoString: string | null) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) return ''

  const pad = (value: number) => value.toString().padStart(2, '0')
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hours = pad(date.getHours())
  const minutes = pad(date.getMinutes())
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

const fromDateTimeLocalValue = (value: string): string | null => {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

export default function PlannerPage() {
  const [origin, setOrigin] = useState<Station | null>(null)
  const [destination, setDestination] = useState<Station | null>(null)
  const [timeType, setTimeType] = useState<'departure' | 'arrival' | 'now'>('now')
  const [selectedTime, setSelectedTime] = useState('')
  const [selectedTransportTypes, setSelectedTransportTypes] = useState<TransportType[]>([])
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false)

  // Calculate route parameters
  const routeParams: RoutePlanParams | undefined =
    origin && destination
      ? {
          origin: origin.id,
          destination: destination.id,
          transport_type: selectedTransportTypes.length > 0 ? selectedTransportTypes : undefined,
          ...(timeType === 'departure' && selectedTime
            ? { departure_time: fromDateTimeLocalValue(selectedTime) || undefined }
            : {}),
          ...(timeType === 'arrival' && selectedTime
            ? { arrival_time: fromDateTimeLocalValue(selectedTime) || undefined }
            : {}),
        }
      : undefined

  const { data, isLoading, error, refetch } = useRoutePlanner({
    params: routeParams,
    enabled: true,
  })

  const { plans } = data?.data || {}

  const handlePlanRoute = () => {
    if (origin && destination) {
      refetch()
    }
  }

  const handleSwapStations = () => {
    setOrigin(destination)
    setDestination(origin)
  }

  const toggleTransportType = (type: TransportType) => {
    setSelectedTransportTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    )
  }

  const getCurrentDateTimeLocal = () => {
    const now = new Date()
    return toDateTimeLocalValue(now.toISOString())
  }

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground">Route Planner</h1>
        <p className="text-gray-400 mt-2">
          Plan your journey across Munich's public transport network
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Route Planning Form */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card rounded-lg border border-border p-6 shadow-sm">
            <div className="space-y-6">
              {/* Origin and Destination */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">From</label>
                  <StationSearchEnhanced
                    onSelect={setOrigin}
                    placeholder="Enter origin station..."
                    showRecentSearches={true}
                  />
                  {origin && (
                    <div className="mt-2 text-sm text-gray-500">Selected: {origin.name}</div>
                  )}
                </div>

                <div className="flex justify-center">
                  <button
                    onClick={handleSwapStations}
                    disabled={!origin || !destination}
                    className="p-2 rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    aria-label="Swap origin and destination"
                  >
                    <svg
                      className="w-5 h-5 text-gray-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                      />
                    </svg>
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">To</label>
                  <StationSearchEnhanced
                    onSelect={setDestination}
                    placeholder="Enter destination station..."
                    showRecentSearches={true}
                  />
                  {destination && (
                    <div className="mt-2 text-sm text-gray-500">Selected: {destination.name}</div>
                  )}
                </div>
              </div>

              {/* Time Options */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Departure/Arrival Time
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => setTimeType('now')}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        timeType === 'now'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      Now
                    </button>
                    <button
                      onClick={() => setTimeType('departure')}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        timeType === 'departure'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      Depart
                    </button>
                    <button
                      onClick={() => setTimeType('arrival')}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        timeType === 'arrival'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      Arrive
                    </button>
                  </div>
                </div>

                {timeType !== 'now' && (
                  <div>
                    <input
                      type="datetime-local"
                      value={selectedTime || getCurrentDateTimeLocal()}
                      onChange={e => setSelectedTime(e.target.value)}
                      className="w-full px-4 py-2 border border-border rounded-lg bg-input text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
                    />
                  </div>
                )}
              </div>

              {/* Advanced Options Toggle */}
              <button
                onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                className="w-full px-4 py-2 text-left text-sm text-primary hover:text-primary/80 flex items-center justify-between"
              >
                <span>Advanced Options</span>
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvancedOptions ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {/* Advanced Options */}
              {showAdvancedOptions && (
                <div className="space-y-4 pt-4 border-t border-border">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-2">
                      Transport Types
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {ALL_TRANSPORT_TYPES.map(type => (
                        <button
                          key={type}
                          onClick={() => toggleTransportType(type)}
                          className={`px-3 py-2 text-xs font-semibold rounded-lg transition-all text-center ${
                            selectedTransportTypes.includes(type)
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-input text-foreground border border-border hover:bg-muted'
                          }`}
                        >
                          {type === 'REGIONAL_BUS' ? 'REGIONAL BUS' : type}
                        </button>
                      ))}
                    </div>
                    {selectedTransportTypes.length > 0 && (
                      <button
                        onClick={() => setSelectedTransportTypes([])}
                        className="mt-2 text-sm text-primary hover:text-primary/80"
                      >
                        Clear transport type filters
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Plan Route Button */}
              <button
                onClick={handlePlanRoute}
                disabled={!origin || !destination || isLoading}
                className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border border-current border-t-transparent"></span>
                    Planning route...
                  </>
                ) : (
                  'Plan Route'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Route Results */}
        <div className="lg:col-span-1">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg">
              <div className="font-medium">Error planning route</div>
              <div className="text-sm mt-1">
                {error instanceof Error ? error.message : 'An unexpected error occurred'}
              </div>
            </div>
          )}

          {plans && plans.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-foreground">Route Options</h2>
              {plans.map((plan, index) => (
                <div
                  key={index}
                  className="bg-card rounded-lg border border-border p-4 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="space-y-3">
                    {/* Route Header */}
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-semibold text-foreground">
                        Option {index + 1}
                      </span>
                      <div className="text-right">
                        <div className="font-semibold text-foreground">
                          {plan.duration_minutes} min
                        </div>
                        <div className="text-sm text-gray-500">
                          {plan.transfers} transfer{plan.transfers !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>

                    {/* Departure/Arrival Times */}
                    {plan.departure && plan.arrival && (
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Departs:</span>
                          <span className="font-medium">
                            {new Date(
                              plan.departure.realtime_time || plan.departure.planned_time || ''
                            ).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Arrives:</span>
                          <span className="font-medium">
                            {new Date(
                              plan.arrival.realtime_time || plan.arrival.planned_time || ''
                            ).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Transport Types Used */}
                    <div className="flex flex-wrap gap-1">
                      {plan.legs.map(
                        (leg, legIndex) =>
                          leg.transport_type && (
                            <span
                              key={legIndex}
                              className={`px-2 py-1 text-xs font-medium rounded ${
                                leg.transport_type === 'UBAHN'
                                  ? 'bg-ubahn text-white'
                                  : leg.transport_type === 'SBAHN'
                                    ? 'bg-sbahn text-white'
                                    : leg.transport_type === 'TRAM'
                                      ? 'bg-tram text-white'
                                      : leg.transport_type === 'BUS' ||
                                          leg.transport_type === 'REGIONAL_BUS'
                                        ? 'bg-bus text-white'
                                        : 'bg-gray-600 text-white'
                              }`}
                            >
                              {leg.line || leg.transport_type}
                            </span>
                          )
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {plans && plans.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <div className="text-4xl mb-4">🗺️</div>
              <div className="font-medium">No routes found</div>
              <div className="text-sm mt-1">Try adjusting your search criteria</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
