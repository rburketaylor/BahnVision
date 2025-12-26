/**
 * Station Page
 * Unified station details page with tabbed interface
 *
 * Tabs:
 * - Overview: Key stats at a glance
 * - Trends: Historical performance charts
 * - Schedule: Live departures (existing DeparturesBoard)
 */

import { useEffect, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router'
import { useDepartures } from '../hooks/useDepartures'
import { useStationStats, useStationTrends } from '../hooks/useStationStats'
import { DeparturesBoard } from '../components/DeparturesBoard'
import type { StationStatsTimeRange, TrendGranularity } from '../types/gtfs'

type StationTab = 'overview' | 'trends' | 'schedule'

const TAB_LABELS: Record<StationTab, string> = {
  overview: 'Overview',
  trends: 'Trends',
  schedule: 'Schedule',
}

const DEFAULT_PAGE_SIZE = 20
const DEFAULT_PAGE_STEP_MINUTES = 30

interface PaginationState {
  pageIndex: number
  pageSize: number
  pageStepMinutes: number
  fromTime: string | null
  live: boolean
}

const toDateTimeLocalValue = (isoString: string | null) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (value: number) => value.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const fromDateTimeLocalValue = (value: string): string | null => {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

function getPerformanceColor(score: number | null): string {
  if (score === null) return 'text-foreground'
  if (score >= 90) return 'text-green-600 dark:text-green-400'
  if (score >= 70) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

function getCancellationColor(rate: number): string {
  if (rate <= 0.02) return 'text-green-600 dark:text-green-400'
  if (rate <= 0.05) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

export function StationPage() {
  const { stationId } = useParams<{ stationId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  // Tab state from URL
  const activeTab = (searchParams.get('tab') as StationTab) || 'overview'

  // Time range for stats (default 24h)
  const statsTimeRange: StationStatsTimeRange =
    (searchParams.get('range') as StationStatsTimeRange) || '24h'
  const trendsGranularity: TrendGranularity =
    (searchParams.get('granularity') as TrendGranularity) || 'hourly'

  // Fetch station stats (only when on overview tab)
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useStationStats(stationId, statsTimeRange, {
    enabled: activeTab === 'overview',
  })

  // Fetch station trends (only when on trends tab)
  const {
    data: trends,
    isLoading: trendsLoading,
    error: trendsError,
  } = useStationTrends(stationId, statsTimeRange, trendsGranularity, {
    enabled: activeTab === 'trends',
  })

  // Pagination state for schedule tab
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

  // Fetch departures (only when on schedule tab)
  const departuresParams = useMemo(() => {
    const baseParams: { stop_id: string; limit: number; offset_minutes?: number } = {
      stop_id: stationId!,
      limit: paginationState.pageSize,
    }
    if (!paginationState.fromTime) {
      baseParams.offset_minutes = paginationState.pageIndex * paginationState.pageStepMinutes
    }
    return baseParams
  }, [stationId, paginationState])

  const {
    data: apiResponse,
    isLoading: departuresLoading,
    error: departuresError,
  } = useDepartures(departuresParams, {
    enabled: !!stationId && activeTab === 'schedule',
    live: paginationState.live,
  })

  const { stop, departures } = apiResponse?.data || {}

  // Update URL when pagination state changes (schedule tab only)
  useEffect(() => {
    if (activeTab !== 'schedule') return

    const newParams = new URLSearchParams(searchParams)
    newParams.set('tab', 'schedule')
    newParams.set('page', paginationState.pageIndex.toString())
    newParams.set('limit', paginationState.pageSize.toString())
    newParams.set('step', paginationState.pageStepMinutes.toString())

    if (paginationState.fromTime) {
      newParams.set('from', paginationState.fromTime)
      newParams.set('live', 'false')
    } else {
      newParams.delete('from')
      newParams.set('live', paginationState.pageIndex === 0 ? 'true' : 'false')
    }

    const currentString = searchParams.toString()
    const newString = newParams.toString()
    if (currentString !== newString) {
      setSearchParams(newParams, { replace: true })
    }
  }, [activeTab, paginationState, searchParams, setSearchParams])

  const setActiveTab = (tab: StationTab) => {
    const newParams = new URLSearchParams()
    newParams.set('tab', tab)
    // Reset schedule params when switching tabs
    if (tab === 'schedule') {
      newParams.set('page', '0')
      newParams.set('limit', DEFAULT_PAGE_SIZE.toString())
      newParams.set('step', DEFAULT_PAGE_STEP_MINUTES.toString())
      newParams.set('live', 'true')
    }
    setSearchParams(newParams, { replace: true })
  }

  const updatePaginationState = (updates: Partial<PaginationState>) => {
    const newState = { ...paginationState, ...updates }
    const newParams = new URLSearchParams(searchParams)

    newParams.set('tab', 'schedule')
    newParams.set('page', newState.pageIndex.toString())
    newParams.set('limit', newState.pageSize.toString())
    newParams.set('step', newState.pageStepMinutes.toString())

    if (newState.fromTime) {
      newParams.set('from', newState.fromTime)
      newParams.delete('offset')
    } else {
      newParams.delete('from')
    }

    newParams.set('live', newState.pageIndex === 0 && !newState.fromTime ? 'true' : 'false')
    setSearchParams(newParams, { replace: true })
  }

  const goToNow = () => updatePaginationState({ pageIndex: 0, fromTime: null, live: true })

  const goToPreviousPage = () => {
    if (paginationState.fromTime) {
      const fromDate = new Date(paginationState.fromTime)
      fromDate.setMinutes(fromDate.getMinutes() - paginationState.pageStepMinutes)
      updatePaginationState({ fromTime: fromDate.toISOString(), live: false })
    } else if (paginationState.pageIndex > 0) {
      updatePaginationState({ pageIndex: paginationState.pageIndex - 1, live: false })
    }
  }

  const goToNextPage = () => {
    if (paginationState.fromTime) {
      const fromDate = new Date(paginationState.fromTime)
      fromDate.setMinutes(fromDate.getMinutes() + paginationState.pageStepMinutes)
      updatePaginationState({ fromTime: fromDate.toISOString(), live: false })
    } else {
      updatePaginationState({ pageIndex: paginationState.pageIndex + 1, live: false })
    }
  }

  const canGoPrevious = paginationState.fromTime !== null || paginationState.pageIndex > 0

  // Determine station name from available sources
  const stationName = stats?.station_name || stop?.name || `Station ${stationId}`

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header with station info and back link */}
      <header className="mb-6">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Map
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{stationName}</h1>
            {stationId && (
              <p className="text-sm text-muted-foreground mt-1">Stop ID: {stationId}</p>
            )}
          </div>
          {activeTab === 'schedule' && (
            <div
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                paginationState.live
                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                  : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
              }`}
            >
              {paginationState.live ? '🟢 Live' : '⏸️ Manual'}
            </div>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-border mb-6">
        <nav className="flex gap-4" aria-label="Station tabs">
          {(Object.keys(TAB_LABELS) as StationTab[]).map(tab => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              }`}
              aria-selected={activeTab === tab}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {statsLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 animate-spin rounded-full border border-gray-300 border-t-primary"></span>
                  <span className="text-muted-foreground">Loading statistics...</span>
                </div>
              </div>
            )}

            {statsError && (
              <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4">
                <p className="text-sm text-destructive">
                  Failed to load statistics: {statsError.message}
                </p>
              </div>
            )}

            {stats && (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard
                    title="Cancellation Rate"
                    value={formatPercent(stats.cancellation_rate)}
                    subtitle={`${stats.cancelled_count} of ${stats.total_departures}`}
                    valueColor={getCancellationColor(stats.cancellation_rate)}
                  />
                  <StatCard
                    title="Delay Rate"
                    value={formatPercent(stats.delay_rate)}
                    subtitle={`${stats.delayed_count} delayed`}
                    valueColor={getCancellationColor(stats.delay_rate)}
                  />
                  <StatCard
                    title="Total Departures"
                    value={stats.total_departures.toLocaleString()}
                    subtitle={`Last ${stats.time_range}`}
                    valueColor="text-foreground"
                  />
                  <StatCard
                    title="Performance"
                    value={
                      stats.performance_score !== null
                        ? `${stats.performance_score.toFixed(0)}%`
                        : '—'
                    }
                    subtitle="Score (100 = perfect)"
                    valueColor={getPerformanceColor(stats.performance_score)}
                  />
                </div>

                {/* Network comparison */}
                {(stats.network_avg_cancellation_rate !== null ||
                  stats.network_avg_delay_rate !== null) && (
                  <div className="rounded-lg border border-border bg-card p-4">
                    <h3 className="text-sm font-semibold text-foreground mb-3">
                      Network Comparison
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Network Avg Cancellation</p>
                        <p className="font-medium">
                          {stats.network_avg_cancellation_rate !== null
                            ? formatPercent(stats.network_avg_cancellation_rate)
                            : '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Network Avg Delay</p>
                        <p className="font-medium">
                          {stats.network_avg_delay_rate !== null
                            ? formatPercent(stats.network_avg_delay_rate)
                            : '—'}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Transport breakdown */}
                {stats.by_transport.length > 0 && (
                  <div className="rounded-lg border border-border bg-card p-4">
                    <h3 className="text-sm font-semibold text-foreground mb-3">
                      By Transport Type
                    </h3>
                    <div className="space-y-2">
                      {stats.by_transport.map(t => (
                        <div
                          key={t.transport_type}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="text-muted-foreground">{t.display_name}</span>
                          <div className="flex gap-4">
                            <span>{t.total_departures} deps</span>
                            <span className={getCancellationColor(t.cancellation_rate)}>
                              {formatPercent(t.cancellation_rate)} cancel
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {!stats && !statsLoading && !statsError && (
              <div className="rounded-lg border border-border bg-card p-6">
                <p className="text-muted-foreground">No statistics available for this station.</p>
              </div>
            )}
          </div>
        )}

        {/* Trends Tab */}
        {activeTab === 'trends' && (
          <div className="space-y-6">
            {trendsLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 animate-spin rounded-full border border-gray-300 border-t-primary"></span>
                  <span className="text-muted-foreground">Loading trends...</span>
                </div>
              </div>
            )}

            {trendsError && (
              <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4">
                <p className="text-sm text-destructive">
                  Failed to load trends: {trendsError.message}
                </p>
              </div>
            )}

            {trends && (
              <>
                {/* Summary stats */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard
                    title="Avg Cancellation"
                    value={formatPercent(trends.avg_cancellation_rate)}
                    subtitle={`Last ${trends.time_range}`}
                    valueColor={getCancellationColor(trends.avg_cancellation_rate)}
                  />
                  <StatCard
                    title="Avg Delay"
                    value={formatPercent(trends.avg_delay_rate)}
                    subtitle={`Last ${trends.time_range}`}
                    valueColor={getCancellationColor(trends.avg_delay_rate)}
                  />
                  <StatCard
                    title="Peak Cancellation"
                    value={formatPercent(trends.peak_cancellation_rate)}
                    subtitle="Highest rate"
                    valueColor={getCancellationColor(trends.peak_cancellation_rate)}
                  />
                  <StatCard
                    title="Peak Delay"
                    value={formatPercent(trends.peak_delay_rate)}
                    subtitle="Highest rate"
                    valueColor={getCancellationColor(trends.peak_delay_rate)}
                  />
                </div>

                {/* Trend data table */}
                {trends.data_points.length > 0 ? (
                  <div className="rounded-lg border border-border bg-card overflow-hidden">
                    <div className="p-4 border-b border-border">
                      <h3 className="text-sm font-semibold text-foreground">
                        {trends.granularity === 'hourly' ? 'Hourly' : 'Daily'} Breakdown
                      </h3>
                    </div>
                    <div className="max-h-96 overflow-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-muted">
                          <tr>
                            <th className="px-4 py-2 text-left font-medium">Time</th>
                            <th className="px-4 py-2 text-right font-medium">Departures</th>
                            <th className="px-4 py-2 text-right font-medium">Cancelled</th>
                            <th className="px-4 py-2 text-right font-medium">Delayed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {trends.data_points.map((point, idx) => (
                            <tr key={idx} className="border-t border-border/50">
                              <td className="px-4 py-2 text-muted-foreground">
                                {new Date(point.timestamp).toLocaleString(undefined, {
                                  dateStyle: trends.granularity === 'daily' ? 'short' : undefined,
                                  timeStyle: trends.granularity === 'hourly' ? 'short' : undefined,
                                })}
                              </td>
                              <td className="px-4 py-2 text-right">{point.total_departures}</td>
                              <td
                                className={`px-4 py-2 text-right ${getCancellationColor(point.cancellation_rate)}`}
                              >
                                {formatPercent(point.cancellation_rate)}
                              </td>
                              <td
                                className={`px-4 py-2 text-right ${getCancellationColor(point.delay_rate)}`}
                              >
                                {formatPercent(point.delay_rate)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-border bg-card p-6">
                    <p className="text-muted-foreground text-center">
                      No trend data available for this time range.
                    </p>
                  </div>
                )}
              </>
            )}

            {!trends && !trendsLoading && !trendsError && (
              <div className="rounded-lg border border-border bg-card p-6">
                <p className="text-muted-foreground">No trend data available for this station.</p>
              </div>
            )}
          </div>
        )}

        {/* Schedule Tab */}
        {activeTab === 'schedule' && (
          <div className="space-y-6">
            {/* Pagination Controls */}
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
                    onChange={e =>
                      updatePaginationState({ pageSize: parseInt(e.target.value, 10) })
                    }
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
                        updatePaginationState({ fromTime: nextIso, pageIndex: 0, live: false })
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
              {departuresLoading && (
                <div className="flex items-center justify-center py-8">
                  <div className="flex items-center gap-2">
                    <span className="h-5 w-5 animate-spin rounded-full border border-gray-300 border-t-primary"></span>
                    <span className="text-muted-foreground">Loading departures...</span>
                  </div>
                </div>
              )}
              {departuresError && (
                <div className="text-center py-8">
                  <p className="text-red-500">
                    Error fetching departures: {departuresError.message}
                  </p>
                </div>
              )}
              {departures && <DeparturesBoard departures={departures} />}
            </section>
          </div>
        )}
      </div>
    </div>
  )
}

/** Simple stat card component */
function StatCard({
  title,
  value,
  subtitle,
  valueColor = 'text-foreground',
}: {
  title: string
  value: string
  subtitle: string
  valueColor?: string
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className={`text-2xl font-bold mt-1 ${valueColor}`}>{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
    </div>
  )
}
