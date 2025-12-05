import { useEffect, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useDepartures } from '../hooks/useDepartures'
import { DeparturesBoard } from '../components/DeparturesBoard'

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

  // Initialize pagination state from URL params
  const paginationState: PaginationState = useMemo(
    () => ({
      pageIndex: parseInt(searchParams.get('page') || '0', 10),
      pageSize: parseInt(searchParams.get('limit') || DEFAULT_PAGE_SIZE.toString(), 10),
      pageStepMinutes: parseInt(
        searchParams.get('step') || DEFAULT_PAGE_STEP_MINUTES.toString(),
        10
      ),
      fromTime: searchParams.get('from'),
      live: searchParams.get('live') !== 'false' && searchParams.get('from') === null,
    }),
    [searchParams]
  )

  // Update URL when state changes
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

    // Only update URL if parameters actually changed (shallow compare)
    const currentParamsString = searchParams.toString()
    const newParamsString = newParams.toString()

    if (currentParamsString !== newParamsString) {
      setSearchParams(newParams, { replace: true })
    }
  }, [paginationState, setSearchParams, searchParams])

  // Determine query parameters based on current pagination state
  const departuresParams = useMemo(() => {
    const baseParams: {
      stop_id: string
      limit: number
      offset_minutes?: number
    } = {
      stop_id: stationId!,
      limit: paginationState.pageSize,
    }

    // Use offset_minutes for time-based pagination
    if (!paginationState.fromTime) {
      baseParams.offset_minutes = paginationState.pageIndex * paginationState.pageStepMinutes
    }

    return baseParams
  }, [stationId, paginationState])

  const {
    data: apiResponse,
    isLoading,
    error,
  } = useDepartures(departuresParams, { enabled: !!stationId, live: paginationState.live })

  const { stop, departures } = apiResponse?.data || {}

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
    <div className="max-w-full">
      {/* Header with stop info */}
      <header className="mb-8">
        {stationId && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold text-foreground">
                Departures for {stop?.name}
              </h1>
              {stop?.id && (
                <p className="text-sm text-gray-400 mt-1">Stop ID: {stop.id}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  paginationState.live
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                }`}
              >
                {paginationState.live ? '🟢 Live' : '⏸️ Manual'}
              </div>
            </div>
          </div>
        )}
      </header>

      <div className="space-y-6 mb-8">
        {/* Pagination Controls - More compact design */}
        <div className="rounded-lg border border-border bg-card p-4 shadow-md">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 items-end">
            {/* Page Navigation */}
            <div className="flex gap-2 col-span-2 sm:col-span-1">
              <button
                onClick={goToPreviousPage}
                disabled={!canGoPrevious}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  canGoPrevious
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'bg-muted text-muted-foreground cursor-not-allowed'
                }`}
              >
                ← Prev
              </button>
              <button
                onClick={goToNextPage}
                className="flex-1 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Next →
              </button>
            </div>

            {/* Page Size Selector */}
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Results</label>
              <select
                value={paginationState.pageSize}
                onChange={e => updatePaginationState({ pageSize: parseInt(e.target.value, 10) })}
                className="w-full px-2 py-2 text-sm border border-border rounded-lg bg-input text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={30}>30</option>
                <option value={40}>40</option>
              </select>
            </div>

            {/* Step Selector */}
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Step</label>
              <select
                value={paginationState.pageStepMinutes}
                onChange={e =>
                  updatePaginationState({ pageStepMinutes: parseInt(e.target.value, 10) })
                }
                className="w-full px-2 py-2 text-sm border border-border rounded-lg bg-input text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              >
                <option value={15}>15m</option>
                <option value={30}>30m</option>
                <option value={60}>1h</option>
              </select>
            </div>

            {/* Time Picker */}
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Time</label>
              <input
                type="datetime-local"
                value={toDateTimeLocalValue(paginationState.fromTime)}
                onChange={e => {
                  if (e.target.value) {
                    const nextIso = fromDateTimeLocalValue(e.target.value)
                    if (!nextIso) return
                    updatePaginationState({
                      fromTime: nextIso,
                      pageIndex: 0,
                      live: false,
                    })
                  } else {
                    goToNow()
                  }
                }}
                className="w-full px-2 py-2 text-sm border border-border rounded-lg bg-input text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              />
            </div>

            {/* Jump to Now */}
            <div>
              <button
                onClick={goToNow}
                className={`w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  paginationState.live
                    ? 'bg-green-600 text-white'
                    : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                }`}
              >
                {paginationState.live ? 'Live' : 'Now'}
              </button>
            </div>
          </div>
        </div>

        {/* Departures Board */}
        <section className="rounded-lg border border-border bg-card p-4 sm:p-6 shadow-lg">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center gap-2">
                <span className="h-5 w-5 animate-spin rounded-full border border-gray-300 border-t-primary"></span>
                <span className="text-gray-400">Loading departures...</span>
              </div>
            </div>
          )}
          {error && (
            <div className="text-center py-8">
              <p className="text-red-500">Error fetching departures: {error.message}</p>
            </div>
          )}
          {departures && <DeparturesBoard departures={departures} />}
        </section>
      </div>
    </div>
  )
}
