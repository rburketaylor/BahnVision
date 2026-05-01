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
import { Activity, ArrowLeft, BarChart3, PauseCircle, RadioTower, TrainFront } from 'lucide-react'
import { useDepartures } from '../hooks/useDepartures'
import { useStationStats, useStationTrends } from '../hooks/useStationStats'
import { DeparturesBoard } from '../components/features/station/DeparturesBoard'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Separator } from '../components/ui/separator'
import { Skeleton } from '../components/ui/skeleton'
import { Avatar, AvatarFallback } from '../components/ui/avatar'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion'
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

function getCancellationBgColor(rate: number): string {
  if (rate <= 0.02) return 'bg-status-healthy'
  if (rate <= 0.05) return 'bg-status-warning'
  return 'bg-status-critical'
}

function toDomIdFragment(value: string | undefined): string {
  return value ? value.replace(/[^A-Za-z0-9_-]/g, '-') : 'unknown'
}

function StatCardSkeleton() {
  return (
    <Card className="border-border/60">
      <CardContent className="p-4">
        <Skeleton className="h-3 w-24 mb-2" />
        <Skeleton className="h-8 w-20 mb-2" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  )
}

export function StationPage() {
  const { stationId } = useParams<{ stationId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTab = (searchParams.get('tab') as StationTab) || 'overview'

  const statsTimeRange: StationStatsTimeRange =
    (searchParams.get('range') as StationStatsTimeRange) || '24h'
  const trendsGranularity: TrendGranularity =
    (searchParams.get('granularity') as TrendGranularity) || 'hourly'

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useStationStats(stationId, statsTimeRange, {
    enabled: activeTab === 'overview',
  })

  const {
    data: trends,
    isLoading: trendsLoading,
    error: trendsError,
  } = useStationTrends(stationId, statsTimeRange, trendsGranularity, {
    enabled: activeTab === 'trends',
  })

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

  const departuresParams = useMemo(() => {
    const baseParams: {
      stop_id: string
      limit: number
      offset_minutes?: number
      from_time?: string
    } = {
      stop_id: stationId!,
      limit: paginationState.pageSize,
    }
    if (paginationState.fromTime) {
      baseParams.from_time = paginationState.fromTime
    } else {
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

  const stationName = stats?.station_name || stop?.name || `Station ${stationId}`
  const scheduleControlIdPrefix = useMemo(
    () => `station-schedule-${toDomIdFragment(stationId)}`,
    [stationId]
  )
  const resultsControlId = `${scheduleControlIdPrefix}-results`
  const stepControlId = `${scheduleControlIdPrefix}-step`
  const timeControlId = `${scheduleControlIdPrefix}-time`

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Card className="overflow-hidden border-border/80 shadow-surface-1">
        <CardHeader className="pb-4">
          <Link
            to="/"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-3"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Map
          </Link>

          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar className="h-14 w-14 bg-primary/10">
                <AvatarFallback className="bg-primary/10 text-primary">
                  <TrainFront className="h-7 w-7" />
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-tiny text-muted-foreground">Station Command</p>
                <CardTitle className="text-h1 text-foreground">{stationName}</CardTitle>
                {stationId && (
                  <p className="mt-0.5 text-small text-muted-foreground font-mono">
                    ID: {stationId}
                  </p>
                )}
              </div>
            </div>

            {activeTab === 'schedule' && (
              <div
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium ${
                  paginationState.live
                    ? 'bg-status-healthy/12 text-status-healthy border border-status-healthy/25'
                    : 'bg-surface-elevated text-muted-foreground border border-border'
                }`}
              >
                {paginationState.live ? (
                  <RadioTower className="h-4 w-4 animate-pulse" />
                ) : (
                  <PauseCircle className="h-4 w-4" />
                )}
                {paginationState.live ? 'Live' : 'Manual'}
              </div>
            )}
          </div>

          <Separator className="mt-5" />

          <nav className="flex flex-wrap gap-2 pt-2" aria-label="Station tabs">
            {(Object.keys(TAB_LABELS) as StationTab[]).map(tab => (
              <Button
                key={tab}
                variant={activeTab === tab ? 'default' : 'ghost'}
                onClick={() => setActiveTab(tab)}
                className={`gap-2 ${activeTab !== tab && 'text-muted-foreground'}`}
                aria-selected={activeTab === tab}
              >
                {tab === 'overview' && <Activity className="h-4 w-4" />}
                {tab === 'trends' && <BarChart3 className="h-4 w-4" />}
                {tab === 'schedule' && <RadioTower className="h-4 w-4" />}
                {TAB_LABELS[tab]}
              </Button>
            ))}
          </nav>
        </CardHeader>
      </Card>

      <div className="space-y-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {statsLoading && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCardSkeleton />
                <StatCardSkeleton />
                <StatCardSkeleton />
                <StatCardSkeleton />
              </div>
            )}

            {statsError && (
              <Card className="border-destructive/30 bg-destructive/5">
                <CardContent className="p-4">
                  <p className="text-sm text-destructive">
                    Failed to load statistics: {statsError.message}
                  </p>
                </CardContent>
              </Card>
            )}

            {stats && (
              <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Cancellation Rate</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(stats.cancellation_rate)}`}
                      >
                        {formatPercent(stats.cancellation_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">
                        {stats.cancelled_count} of {stats.total_departures}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Delay Rate</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(stats.delay_rate)}`}
                      >
                        {formatPercent(stats.delay_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">
                        {stats.delayed_count} delayed
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Total Departures</p>
                      <p className="text-h1 tabular-nums">
                        {stats.total_departures.toLocaleString()}
                      </p>
                      <p className="text-small text-muted-foreground">Last {stats.time_range}</p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Performance</p>
                      <p
                        className={`text-h1 tabular-nums ${getPerformanceColor(stats.performance_score)}`}
                      >
                        {stats.performance_score !== null
                          ? `${stats.performance_score.toFixed(0)}%`
                          : '—'}
                      </p>
                      <p className="text-small text-muted-foreground">Score (100 = perfect)</p>
                    </CardContent>
                  </Card>
                </div>

                <Accordion
                  type="multiple"
                  defaultValue={['network', 'transport']}
                  className="space-y-4"
                >
                  {(stats.network_avg_cancellation_rate !== null ||
                    stats.network_avg_delay_rate !== null) && (
                    <AccordionItem value="network" className="border-border rounded-lg px-4">
                      <AccordionTrigger className="hover:no-underline">
                        <span className="text-sm font-semibold">Network Comparison</span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="grid grid-cols-2 gap-4 pt-2 pb-1">
                          <div>
                            <p className="text-small text-muted-foreground">
                              Network Avg Cancellation
                            </p>
                            <p className="font-semibold text-foreground">
                              {stats.network_avg_cancellation_rate !== null
                                ? formatPercent(stats.network_avg_cancellation_rate)
                                : '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-small text-muted-foreground">Network Avg Delay</p>
                            <p className="font-semibold text-foreground">
                              {stats.network_avg_delay_rate !== null
                                ? formatPercent(stats.network_avg_delay_rate)
                                : '—'}
                            </p>
                          </div>
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  )}

                  {stats.by_transport.length > 0 && (
                    <AccordionItem value="transport" className="border-border rounded-lg px-4">
                      <AccordionTrigger className="hover:no-underline">
                        <span className="text-sm font-semibold">By Transport Type</span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-3 pt-2 pb-1">
                          {stats.by_transport.map(t => (
                            <div
                              key={t.transport_type}
                              className="flex items-center justify-between"
                            >
                              <div className="flex items-center gap-3">
                                <div
                                  className={`h-2 w-2 rounded-full ${getCancellationBgColor(t.cancellation_rate)}`}
                                />
                                <span className="text-sm text-foreground">{t.display_name}</span>
                              </div>
                              <div className="flex gap-4 text-sm">
                                <span className="text-muted-foreground tabular-nums">
                                  {t.total_departures} deps
                                </span>
                                <span className={getCancellationColor(t.cancellation_rate)}>
                                  {formatPercent(t.cancellation_rate)} cancel
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  )}
                </Accordion>
              </>
            )}

            {!stats && !statsLoading && !statsError && (
              <Card className="border-border/60">
                <CardContent className="p-6">
                  <p className="text-muted-foreground">No statistics available for this station.</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'trends' && (
          <div className="space-y-6">
            {trendsLoading && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                </div>
                <Card className="border-border/60">
                  <CardContent className="p-4">
                    <Skeleton className="h-64 w-full" />
                  </CardContent>
                </Card>
              </div>
            )}

            {trendsError && (
              <Card className="border-destructive/30 bg-destructive/5">
                <CardContent className="p-4">
                  <p className="text-sm text-destructive">
                    Failed to load trends: {trendsError.message}
                  </p>
                </CardContent>
              </Card>
            )}

            {trends && (
              <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Avg Cancellation</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(trends.avg_cancellation_rate)}`}
                      >
                        {formatPercent(trends.avg_cancellation_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">Last {trends.time_range}</p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Avg Delay</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(trends.avg_delay_rate)}`}
                      >
                        {formatPercent(trends.avg_delay_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">Last {trends.time_range}</p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Peak Cancellation</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(trends.peak_cancellation_rate)}`}
                      >
                        {formatPercent(trends.peak_cancellation_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">Highest rate</p>
                    </CardContent>
                  </Card>
                  <Card className="border-border/60">
                    <CardContent className="p-4 space-y-1">
                      <p className="text-tiny text-muted-foreground">Peak Delay</p>
                      <p
                        className={`text-h1 tabular-nums ${getCancellationColor(trends.peak_delay_rate)}`}
                      >
                        {formatPercent(trends.peak_delay_rate)}
                      </p>
                      <p className="text-small text-muted-foreground">Highest rate</p>
                    </CardContent>
                  </Card>
                </div>

                {trends.data_points.length > 0 ? (
                  <Card className="border-border/60 overflow-hidden">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">
                        {trends.granularity === 'hourly' ? 'Hourly' : 'Daily'} Breakdown
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="max-h-96 overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="sticky top-0 bg-surface/95 backdrop-blur">
                            <tr className="border-b border-border">
                              <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                                Time
                              </th>
                              <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                                Departures
                              </th>
                              <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                                Cancelled
                              </th>
                              <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                                Delayed
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {trends.data_points.map((point, idx) => (
                              <tr key={idx} className="border-b border-border/40">
                                <td className="px-4 py-2.5 text-muted-foreground">
                                  {new Date(point.timestamp).toLocaleString(undefined, {
                                    dateStyle: trends.granularity === 'daily' ? 'short' : undefined,
                                    timeStyle:
                                      trends.granularity === 'hourly' ? 'short' : undefined,
                                  })}
                                </td>
                                <td className="px-4 py-2.5 text-right tabular-nums text-foreground">
                                  {point.total_departures}
                                </td>
                                <td
                                  className={`px-4 py-2.5 text-right tabular-nums ${getCancellationColor(point.cancellation_rate)}`}
                                >
                                  {formatPercent(point.cancellation_rate)}
                                </td>
                                <td
                                  className={`px-4 py-2.5 text-right tabular-nums ${getCancellationColor(point.delay_rate)}`}
                                >
                                  {formatPercent(point.delay_rate)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="border-border/60">
                    <CardContent className="p-6">
                      <p className="text-muted-foreground text-center">
                        No trend data available for this time range.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {!trends && !trendsLoading && !trendsError && (
              <Card className="border-border/60">
                <CardContent className="p-6">
                  <p className="text-muted-foreground">No trend data available for this station.</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="space-y-6">
            <Card className="border-border/60">
              <CardContent className="p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 items-end">
                  <div className="flex gap-2 col-span-2 sm:col-span-1">
                    <Button
                      variant="outline"
                      onClick={goToPreviousPage}
                      disabled={!canGoPrevious}
                      className="flex-1"
                      size="sm"
                    >
                      ← Prev
                    </Button>
                    <Button onClick={goToNextPage} className="flex-1" size="sm">
                      Next →
                    </Button>
                  </div>

                  <div>
                    <label
                      htmlFor={resultsControlId}
                      className="mb-1 block text-tiny text-muted-foreground"
                    >
                      Results
                    </label>
                    <select
                      id={resultsControlId}
                      value={paginationState.pageSize}
                      onChange={e =>
                        updatePaginationState({ pageSize: parseInt(e.target.value, 10) })
                      }
                      className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={30}>30</option>
                      <option value={40}>40</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor={stepControlId}
                      className="mb-1 block text-tiny text-muted-foreground"
                    >
                      Step
                    </label>
                    <select
                      id={stepControlId}
                      value={paginationState.pageStepMinutes}
                      onChange={e =>
                        updatePaginationState({ pageStepMinutes: parseInt(e.target.value, 10) })
                      }
                      className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value={15}>15m</option>
                      <option value={30}>30m</option>
                      <option value={60}>1h</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor={timeControlId}
                      className="mb-1 block text-tiny text-muted-foreground"
                    >
                      Time
                    </label>
                    <input
                      id={timeControlId}
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
                      className="w-full rounded-md border border-input bg-input px-2.5 py-2 text-sm focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-tiny text-muted-foreground">&nbsp;</label>
                    <Button
                      onClick={goToNow}
                      variant={paginationState.live ? 'default' : 'secondary'}
                      className="w-full"
                      size="sm"
                    >
                      {paginationState.live ? 'Live' : 'Now'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/60 overflow-hidden">
              {departuresLoading && (
                <CardContent className="p-8">
                  <div className="space-y-3">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                </CardContent>
              )}
              {departuresError && (
                <CardContent className="p-6">
                  <p className="text-status-critical text-center">
                    Error fetching departures: {departuresError.message}
                  </p>
                </CardContent>
              )}
              {departures && <DeparturesBoard departures={departures} />}
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
