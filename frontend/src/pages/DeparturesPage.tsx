import { useState, useEffect, useMemo, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useDepartures } from '../hooks/useDepartures'
import { DeparturesBoard } from '../components/DeparturesBoard'
import type { TransportType } from '../types/api'

// SEV temporarily removed due to MVG API 400 errors - may need station-specific handling
const ALL_TRANSPORT_TYPES: TransportType[] = ['BAHN', 'SBAHN', 'UBAHN', 'TRAM', 'BUS', 'REGIONAL_BUS', 'SCHIFF']
const DEFAULT_PAGE_SIZE = 20
const DEFAULT_PAGE_STEP_MINUTES = 30

const toDateTimeLocalValue = (isoString: string | null) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

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
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date.toISOString()
}

interface PaginationState {
  pageIndex: number
  pageSize: number
  pageStepMinutes: number
  fromTime: string | null
  live: boolean
}

export function DeparturesPage() {
  const { stationId } = useParams<{ stationId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedTransportTypes, setSelectedTransportTypes] = useState<TransportType[]>([])

  // Debouncing for transport type changes to prevent cascading API calls
  const [debouncedTransportTypes, setDebouncedTransportTypes] = useState<TransportType[]>([])
  const debounceTimeoutRef = useRef<number | null>(null)
  const [isFilterUpdating, setIsFilterUpdating] = useState(false)

  // Initialize transport types from URL params on mount
  useEffect(() => {
    const transportParam = searchParams.get('transport_type')
    if (transportParam) {
      const types = transportParam.split(',').filter(Boolean) as TransportType[]
      setSelectedTransportTypes(types)
      setDebouncedTransportTypes(types)
    }
  }, [searchParams])

  // Initialize pagination state from URL params
  const paginationState: PaginationState = useMemo(() => ({
    pageIndex: parseInt(searchParams.get('page') || '0', 10),
    pageSize: parseInt(searchParams.get('limit') || DEFAULT_PAGE_SIZE.toString(), 10),
    pageStepMinutes: parseInt(searchParams.get('step') || DEFAULT_PAGE_STEP_MINUTES.toString(), 10),
    fromTime: searchParams.get('from'),
    live: searchParams.get('live') !== 'false' && searchParams.get('from') === null,
  }), [searchParams])

  // Debounced transport types for API calls (prevents cascading requests)
  const sortedDebouncedTransportTypes = useMemo(() => {
    return [...debouncedTransportTypes].sort()
  }, [debouncedTransportTypes])

  // Update URL when state changes - use debounced transport types
  useEffect(() => {
    const newParams = new URLSearchParams()

    // Always include station identifier implicitly via route
    newParams.set('page', paginationState.pageIndex.toString())
    newParams.set('limit', paginationState.pageSize.toString())
    newParams.set('step', paginationState.pageStepMinutes.toString())

    if (paginationState.fromTime) {
      newParams.set('from', paginationState.fromTime)
      newParams.set('live', 'false')
    } else if (paginationState.pageIndex === 0) {
      newParams.set('live', 'true')
    } else {
      newParams.set('live', 'false')
    }

    // Only use debounced transport types for URL
    if (sortedDebouncedTransportTypes.length > 0) {
      newParams.set('transport_type', sortedDebouncedTransportTypes.join(','))
    } else {
      newParams.delete('transport_type')
    }

    // Only update URL if parameters actually changed (shallow compare)
    const currentParamsString = searchParams.toString()
    const newParamsString = newParams.toString()

    if (currentParamsString !== newParamsString) {
      setSearchParams(newParams, { replace: true })
    }
  }, [paginationState, sortedDebouncedTransportTypes, setSearchParams, searchParams])

  // Debounce transport type changes
  useEffect(() => {
    // Clear existing timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current)
    }

    // Check if transport types actually changed
    const currentTypes = JSON.stringify(selectedTransportTypes.sort())
    const debouncedTypes = JSON.stringify(debouncedTransportTypes.sort())

    if (currentTypes !== debouncedTypes) {
      setIsFilterUpdating(true)

      // Dynamic debounce delay based on complexity
      const debounceDelay = selectedTransportTypes.length > 4 ? 800 :
                           selectedTransportTypes.length > 2 ? 500 : 300

      // Set new timeout
      debounceTimeoutRef.current = setTimeout(() => {
        const sortedTypes = [...selectedTransportTypes].sort()
        setDebouncedTransportTypes(sortedTypes)
        setIsFilterUpdating(false)
      }, debounceDelay)
    }

    // Cleanup
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [selectedTransportTypes, debouncedTransportTypes])

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [])

  // Determine query parameters based on current pagination state
  const departuresParams = useMemo(() => {
    const baseParams: {
      station: string
      limit: number
      offset?: number
      from?: string
      transport_type?: TransportType[]
    } = {
      station: stationId!,
      limit: paginationState.pageSize,
      transport_type: sortedDebouncedTransportTypes.length > 0 ? sortedDebouncedTransportTypes : undefined,
    }

    if (paginationState.fromTime) {
      baseParams.from = paginationState.fromTime
    } else {
      baseParams.offset = paginationState.pageIndex * paginationState.pageStepMinutes
    }

    return baseParams
  }, [stationId, paginationState, sortedDebouncedTransportTypes])

  const { data: apiResponse, isLoading, error } = useDepartures(
    departuresParams,
    { enabled: !!stationId, live: paginationState.live }
  )

  const { station, departures } = apiResponse?.data || {}

  const toggleTransportType = (transportType: TransportType) => {
    setSelectedTransportTypes((prev) =>
      prev.includes(transportType) ? prev.filter((t) => t !== transportType) : [...prev, transportType]
    )
  }

  const updatePaginationState = (updates: Partial<PaginationState>) => {
    const newState = { ...paginationState, ...updates }
    const newParams = new URLSearchParams(searchParams)

    newParams.set('page', newState.pageIndex.toString())
    newParams.set('limit', newState.pageSize.toString())
    newParams.set('step', newState.pageStepMinutes.toString())

    if (newState.fromTime) {
      newParams.set('from', newState.fromTime)
      newParams.delete('offset')
    } else {
      newParams.delete('from')
    }

    if (newState.pageIndex === 0 && !newState.fromTime) {
      newParams.set('live', 'true')
    } else {
      newParams.set('live', 'false')
    }

    // Only update URL if parameters actually changed (shallow compare)
    const currentParamsString = searchParams.toString()
    const newParamsString = newParams.toString()

    if (currentParamsString !== newParamsString) {
      setSearchParams(newParams, { replace: true })
    }
  }

  const goToNow = () => {
    updatePaginationState({
      pageIndex: 0,
      fromTime: null,
      live: true,
    })
  }

  const goToPreviousPage = () => {
    if (paginationState.fromTime) {
      // If we have a from_time, go back by pageStepMinutes
      const fromDate = new Date(paginationState.fromTime)
      fromDate.setMinutes(fromDate.getMinutes() - paginationState.pageStepMinutes)
      updatePaginationState({
        fromTime: fromDate.toISOString(),
        live: false,
      })
    } else if (paginationState.pageIndex > 0) {
      updatePaginationState({
        pageIndex: paginationState.pageIndex - 1,
        live: false,
      })
    }
  }

  const goToNextPage = () => {
    if (paginationState.fromTime) {
      // If we have a from_time, advance by pageStepMinutes
      const fromDate = new Date(paginationState.fromTime)
      fromDate.setMinutes(fromDate.getMinutes() + paginationState.pageStepMinutes)
      updatePaginationState({
        fromTime: fromDate.toISOString(),
        live: false,
      })
    } else {
      updatePaginationState({
        pageIndex: paginationState.pageIndex + 1,
        live: false,
      })
    }
  }

  const canGoPrevious = paginationState.fromTime !== null || paginationState.pageIndex > 0

  return (
    <div className="space-y-8">
      <header>
        {stationId && <h1 className="text-4xl font-bold text-foreground">Departures for {station?.name}</h1>}
      </header>

      {/* Transport Type Filters */}
      <div className="rounded-lg border border-border bg-card p-4 shadow-md">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Transport Types</h3>
          <div className="flex items-center gap-2">
            {isFilterUpdating && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <span className="h-3 w-3 animate-spin rounded-full border border-gray-300 border-t-blue-500"></span>
                {sortedDebouncedTransportTypes.length > 3 ? 'Loading complex filters...' : 'Updating...'}
              </span>
            )}
            {selectedTransportTypes.length > 0 && (
              <button
                onClick={() => {
                  setSelectedTransportTypes([])
                  // Immediately clear debounced state as well
                  setDebouncedTransportTypes([])
                  setIsFilterUpdating(false)
                  if (debounceTimeoutRef.current) {
                    clearTimeout(debounceTimeoutRef.current)
                    debounceTimeoutRef.current = null
                  }
                }}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Reset filters
              </button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {ALL_TRANSPORT_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => toggleTransportType(type)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                selectedTransportTypes.includes(type)
                  ? 'bg-gray-900 text-white border border-gray-900 shadow-sm'
                  : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-100'
              }`}
            >
              {type === 'REGIONAL_BUS' ? 'REGIONAL BUS' : type}
            </button>
          ))}
        </div>
      </div>

      {/* Pagination Controls */}
      <div className="rounded-lg border border-border bg-card p-4 shadow-md">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 items-center">
          {/* Page Navigation */}
          <div className="flex gap-2">
            <button
              onClick={goToPreviousPage}
              disabled={!canGoPrevious}
              className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                canGoPrevious
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              Prev
            </button>
            <button
              onClick={goToNextPage}
              className="px-3 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Next
            </button>
          </div>

          {/* Page Size Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Page Size</label>
            <select
              value={paginationState.pageSize}
              onChange={(e) => updatePaginationState({ pageSize: parseInt(e.target.value, 10) })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={30}>30</option>
              <option value={40}>40</option>
            </select>
          </div>

          {/* Step Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Step (min)</label>
            <select
              value={paginationState.pageStepMinutes}
              onChange={(e) => updatePaginationState({ pageStepMinutes: parseInt(e.target.value, 10) })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={15}>15</option>
              <option value={30}>30</option>
              <option value={60}>60</option>
            </select>
          </div>

          {/* Time Picker */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Start Time</label>
            <input
              type="datetime-local"
              value={toDateTimeLocalValue(paginationState.fromTime)}
              onChange={(e) => {
                if (e.target.value) {
                  const nextIso = fromDateTimeLocalValue(e.target.value)
                  if (!nextIso) {
                    return
                  }
                  updatePaginationState({
                    fromTime: nextIso,
                    pageIndex: 0,
                    live: false,
                  })
                } else {
                  goToNow()
                }
              }}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Jump to Now */}
          <div>
            <button
              onClick={goToNow}
              className={`w-full px-3 py-2 rounded text-sm font-medium transition-colors ${
                paginationState.live
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-600 text-white hover:bg-gray-700'
              }`}
            >
              {paginationState.live ? 'Live' : 'Jump to Now'}
            </button>
          </div>

          {/* Live Status */}
          <div className="text-center">
            <div className={`text-xs font-medium ${
              paginationState.live ? 'text-green-600' : 'text-gray-500'
            }`}>
              {paginationState.live ? '🟢 Auto-refresh' : '⏸️ Manual'}
            </div>
            {paginationState.fromTime && (
              <div className="text-xs text-gray-500">
                From: {new Date(paginationState.fromTime).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Departures Board */}
      <section className="rounded-lg border border-border bg-card p-6 shadow-lg">
        {isLoading && <p className="text-center text-gray-400">Loading departures...</p>}
        {error && <p className="text-center text-red-500">Error fetching departures: {error.message}</p>}
        {departures && <DeparturesBoard departures={departures} />}
      </section>
    </div>
  )
}
