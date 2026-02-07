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
import { Activity, BarChart3, ChevronLeft, PauseCircle, RadioTower } from 'lucide-react'
import { useDepartures } from '../hooks/useDepartures'
import { useStationStats, useStationTrends } from '../hooks/useStationStats'
import { DeparturesBoard } from '../components/features/station/DeparturesBoard'
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
  if (score >= 90) return 'text-status-healthy'
  if (score >= 70) return 'text-status-warning'
  return 'text-status-critical'
}

function getCancellationColor(rate: number): string {
  if (rate <= 0.02) return 'text-status-healthy'
  if (rate <= 0.05) return 'text-status-warning'
  return 'text-status-critical'
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
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="rounded-lg border border-border bg-card p-5 shadow-surface-1">
        <Link
          to="/"
          className="mb-4 inline-flex items-center gap-1.5 text-small text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Map
        </Link>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-tiny text-muted-foreground">Station Command</p>
            <h1 className="text-h1 text-foreground">{stationName}</h1>
            {stationId && (
              <p className="mt-1 text-small text-muted-foreground">Stop ID: {stationId}</p>
            )}
          </div>

          {activeTab === 'schedule' && (
            <div
              className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-small font-semibold uppercase tracking-[0.04em] ${
                paginationState.live
                  ? 'border-status-healthy/30 bg-status-healthy/12 text-status-healthy'
                  : 'border-status-neutral/30 bg-surface-elevated text-muted-foreground'
              }`}
            >
              {paginationState.live ? (
                <RadioTower className="h-4 w-4 animate-status-pulse" />
              ) : (
                <PauseCircle className="h-4 w-4" />
              )}
              {paginationState.live ? 'Live' : 'Manual'}
            </div>
          )}
        </div>

        <div className="mt-5 border-t border-border pt-4">
          <nav className="flex flex-wrap gap-2" aria-label="Station tabs">
            {(Object.keys(TAB_LABELS) as StationTab[]).map(tab => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-2 text-small font-semibold uppercase tracking-[0.05em] transition-colors ${
                  activeTab === tab
                    ? 'border-primary/40 bg-primary/12 text-primary'
                    : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated hover:text-foreground'
                }`}
                aria-selected={activeTab === tab}
              >
                {tab === 'overview' && <Activity className="h-4 w-4" />}
                {tab === 'trends' && <BarChart3 className="h-4 w-4" />}
                {tab === 'schedule' && <RadioTower className="h-4 w-4" />}
                {TAB_LABELS[tab]}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {statsLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 animate-spin rounded-full border border-border border-t-primary"></span>
                  <span className="text-muted-foreground">Loading statistics...</span>
                </div>
              </div>
            )}

            {statsError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4">
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
                  <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
                    <h3 className="mb-3 text-small font-semibold uppercase tracking-[0.05em] text-muted-foreground">
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
                  <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
                    <h3 className="mb-3 text-small font-semibold uppercase tracking-[0.05em] text-muted-foreground">
                      By Transport Type
                    </h3>
                    <div className="space-y-2">
                      {stats.by_transport.map(t => (
                        <div
                          key={t.transport_type}
                          className="flex items-center justify-between border-b border-border/60 py-2 text-sm last:border-b-0"
                        >
                          <span className="text-muted-foreground">{t.display_name}</span>
                          <div className="flex gap-4">
                            <span className="tabular-nums">{t.total_departures} deps</span>
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
              <div className="rounded-md border border-border bg-card p-6">
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
                  <span className="h-5 w-5 animate-spin rounded-full border border-border border-t-primary"></span>
                  <span className="text-muted-foreground">Loading trends...</span>
                </div>
              </div>
            )}

            {trendsError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4">
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
                  <div className="overflow-hidden rounded-md border border-border bg-card shadow-surface-1">
                    <div className="border-b border-border p-4">
                      <h3 className="text-small font-semibold uppercase tracking-[0.05em] text-muted-foreground">
                        {trends.granularity === 'hourly' ? 'Hourly' : 'Daily'} Breakdown
                      </h3>
                    </div>
                    <div className="max-h-96 overflow-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-surface-muted/90 backdrop-blur">
                          <tr>
                            <th className="px-4 py-2 text-left font-medium">Time</th>
                            <th className="px-4 py-2 text-right font-medium">Departures</th>
                            <th className="px-4 py-2 text-right font-medium">Cancelled</th>
                            <th className="px-4 py-2 text-right font-medium">Delayed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {trends.data_points.map((point, idx) => (
                            <tr key={idx} className="border-t border-border/60">
                              <td className="px-4 py-2 text-muted-foreground">
                                {new Date(point.timestamp).toLocaleString(undefined, {
                                  dateStyle: trends.granularity === 'daily' ? 'short' : undefined,
                                  timeStyle: trends.granularity === 'hourly' ? 'short' : undefined,
                                })}
                              </td>
                              <td className="px-4 py-2 text-right tabular-nums">
                                {point.total_departures}
                              </td>
                              <td
                                className={`px-4 py-2 text-right tabular-nums ${getCancellationColor(point.cancellation_rate)}`}
                              >
                                {formatPercent(point.cancellation_rate)}
                              </td>
                              <td
                                className={`px-4 py-2 text-right tabular-nums ${getCancellationColor(point.delay_rate)}`}
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
                  <div className="rounded-md border border-border bg-card p-6">
                    <p className="text-muted-foreground text-center">
                      No trend data available for this time range.
                    </p>
                  </div>
                )}
              </>
            )}

            {!trends && !trendsLoading && !trendsError && (
              <div className="rounded-md border border-border bg-card p-6">
                <p className="text-muted-foreground">No trend data available for this station.</p>
              </div>
            )}
          </div>
        )}

        {/* Schedule Tab */}
        {activeTab === 'schedule' && (
          <div className="space-y-6">
            {/* Pagination Controls */}
            <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 items-end">
                {/* Page Navigation */}
                <div className="flex gap-2 col-span-2 sm:col-span-1">
                  <button
                    onClick={goToPreviousPage}
                    disabled={!canGoPrevious}
                    className={`btn-bvv flex-1 rounded-md px-3 py-2 text-sm font-semibold transition-colors ${
                      canGoPrevious
                        ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                        : 'bg-surface-elevated text-muted-foreground cursor-not-allowed'
                    }`}
                  >
                    ← Prev
                  </button>
                  <button
                    onClick={goToNextPage}
                    className="btn-bvv flex-1 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
                  >
                    Next →
                  </button>
                </div>

                {/* Page Size Selector */}
                <div>
                  <label className="mb-1 block text-tiny text-muted-foreground">Results</label>
                  <select
                    value={paginationState.pageSize}
                    onChange={e =>
                      updatePaginationState({ pageSize: parseInt(e.target.value, 10) })
                    }
                    className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm text-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={30}>30</option>
                    <option value={40}>40</option>
                  </select>
                </div>

                {/* Step Selector */}
                <div>
                  <label className="mb-1 block text-tiny text-muted-foreground">Step</label>
                  <select
                    value={paginationState.pageStepMinutes}
                    onChange={e =>
                      updatePaginationState({ pageStepMinutes: parseInt(e.target.value, 10) })
                    }
                    className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm text-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value={15}>15m</option>
                    <option value={30}>30m</option>
                    <option value={60}>1h</option>
                  </select>
                </div>

                {/* Time Picker */}
                <div>
                  <label className="mb-1 block text-tiny text-muted-foreground">Time</label>
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
                    className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm text-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                {/* Jump to Now */}
                <div>
                  <button
                    onClick={goToNow}
                    className={`btn-bvv w-full rounded-md px-3 py-2 text-sm font-semibold transition-colors ${
                      paginationState.live
                        ? 'bg-status-healthy text-white'
                        : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                    }`}
                  >
                    {paginationState.live ? 'Live' : 'Now'}
                  </button>
                </div>
              </div>
            </div>

            {/* Departures Board */}
            <section className="rounded-md border border-border bg-card p-4 shadow-surface-1 sm:p-6">
              {departuresLoading && (
                <div className="flex items-center justify-center py-8">
                  <div className="flex items-center gap-2">
                    <span className="h-5 w-5 animate-spin rounded-full border border-border border-t-primary"></span>
                    <span className="text-muted-foreground">Loading departures...</span>
                  </div>
                </div>
              )}
              {departuresError && (
                <div className="text-center py-8">
                  <p className="text-status-critical">
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
    <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
      <p className="text-tiny text-muted-foreground">{title}</p>
      <p className={`mt-1 text-h1 tabular-nums ${valueColor}`}>{value}</p>
      <p className="mt-1 text-small text-muted-foreground">{subtitle}</p>
    </div>
  )
}
