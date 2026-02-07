/**
 * Ingestion Tab
 * GTFS data pipeline status (static feed + realtime harvester)
 */

import { useState, type ReactNode } from 'react'
import { Database, Package, RadioTower } from 'lucide-react'
import { apiClient } from '../../../services/api'
import { useAutoRefresh } from '../../../hooks/useAutoRefresh'
import type { IngestionStatus } from '../../../types/ingestion'
import { ErrorCard, RefreshButton } from '../../shared'

const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/

export default function IngestionTab() {
  const [status, setStatus] = useState<IngestionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.getIngestionStatus()
      setStatus(response.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch ingestion status')
    } finally {
      setLoading(false)
    }
  }

  useAutoRefresh({ callback: fetchStatus, enabled: true, runOnMount: true })

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    if (DATE_ONLY_PATTERN.test(dateStr)) {
      return new Date(`${dateStr}T00:00:00Z`).toLocaleDateString(undefined, { timeZone: 'UTC' })
    }
    return new Date(dateStr).toLocaleString()
  }

  const formatShortDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    if (DATE_ONLY_PATTERN.test(dateStr)) {
      return new Date(`${dateStr}T00:00:00Z`).toLocaleDateString(undefined, { timeZone: 'UTC' })
    }
    return new Date(dateStr).toLocaleDateString()
  }

  if (error) {
    return (
      <ErrorCard title="Failed to load ingestion status" message={error} onRetry={fetchStatus} />
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <RefreshButton onClick={fetchStatus} loading={loading} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-card p-5 shadow-surface-1">
          <div className="mb-4 flex items-center gap-2">
            <Package className="h-5 w-5 text-primary" />
            <h2 className="text-h2 text-foreground">GTFS Static Feed</h2>
          </div>

          {loading && !status ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-surface-muted" />
              ))}
            </div>
          ) : status?.gtfs_feed ? (
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-elevated px-2.5 py-1.5 text-small">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    status.gtfs_feed.is_expired
                      ? 'bg-status-critical'
                      : status.gtfs_feed.feed_id
                        ? 'bg-status-healthy animate-status-pulse'
                        : 'bg-status-neutral'
                  }`}
                />
                <span className="font-semibold text-foreground">
                  {status.gtfs_feed.is_expired
                    ? 'Feed Expired'
                    : status.gtfs_feed.feed_id
                      ? 'Feed Active'
                      : 'No Feed Loaded'}
                </span>
              </div>

              <div className="space-y-2 text-small">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Last Import</span>
                  <span className="text-foreground tabular-nums">
                    {formatDate(status.gtfs_feed.downloaded_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Valid From</span>
                  <span className="text-foreground tabular-nums">
                    {formatShortDate(status.gtfs_feed.feed_start_date)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Valid Until</span>
                  <span
                    className={
                      status.gtfs_feed.is_expired
                        ? 'text-status-critical tabular-nums'
                        : 'text-foreground tabular-nums'
                    }
                  >
                    {formatShortDate(status.gtfs_feed.feed_end_date)}
                  </span>
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <h4 className="mb-3 text-tiny text-muted-foreground">Record Counts</h4>
                <div className="grid grid-cols-3 gap-2">
                  <MetricTile
                    icon={<Database className="h-3.5 w-3.5" />}
                    label="Stops"
                    value={status.gtfs_feed.stop_count}
                  />
                  <MetricTile
                    icon={<Database className="h-3.5 w-3.5" />}
                    label="Routes"
                    value={status.gtfs_feed.route_count}
                  />
                  <MetricTile
                    icon={<Database className="h-3.5 w-3.5" />}
                    label="Trips"
                    value={status.gtfs_feed.trip_count}
                  />
                </div>
              </div>
            </div>
          ) : (
            <p className="text-small text-muted-foreground">No feed data available.</p>
          )}
        </div>

        <div className="rounded-md border border-border bg-card p-5 shadow-surface-1">
          <div className="mb-4 flex items-center gap-2">
            <RadioTower className="h-5 w-5 text-primary" />
            <h2 className="text-h2 text-foreground">Realtime Harvester</h2>
          </div>

          {loading && !status ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-surface-muted" />
              ))}
            </div>
          ) : status?.gtfs_rt_harvester ? (
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-elevated px-2.5 py-1.5 text-small">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    status.gtfs_rt_harvester.is_running
                      ? 'bg-status-healthy animate-status-pulse'
                      : 'bg-status-neutral'
                  }`}
                />
                <span className="font-semibold text-foreground">
                  {status.gtfs_rt_harvester.is_running ? 'Running' : 'Stopped'}
                </span>
              </div>

              <div className="space-y-2 text-small">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Last Harvest</span>
                  <span className="text-foreground tabular-nums">
                    {status.gtfs_rt_harvester.last_harvest_at
                      ? formatDate(status.gtfs_rt_harvester.last_harvest_at)
                      : 'Never'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Stations Updated (Last)</span>
                  <span className="text-foreground tabular-nums">
                    {status.gtfs_rt_harvester.stations_updated_last_harvest.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Total Stats Records</span>
                  <span className="text-foreground tabular-nums">
                    {status.gtfs_rt_harvester.total_stats_records.toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <div className="flex items-center gap-3">
                  <div className="h-2 flex-1 overflow-hidden rounded bg-surface-muted">
                    <div
                      className={`h-full transition-all duration-300 ${
                        status.gtfs_rt_harvester.is_running
                          ? 'w-full bg-status-healthy'
                          : 'w-[8%] bg-status-neutral'
                      }`}
                    />
                  </div>
                  <span className="text-tiny text-muted-foreground">
                    {status.gtfs_rt_harvester.is_running ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-small text-muted-foreground">No harvester data available.</p>
          )}
        </div>
      </div>

      <div className="text-center text-small text-muted-foreground">
        <p>Data refreshes automatically every 30 seconds.</p>
        <p className="mt-1 tabular-nums">Last updated: {new Date().toLocaleTimeString()}</p>
      </div>
    </div>
  )
}

function MetricTile({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-surface-elevated p-3 text-center">
      <div className="mb-1 inline-flex items-center gap-1 text-muted-foreground">
        {icon}
        <span className="text-tiny">{label}</span>
      </div>
      <div className="text-h3 tabular-nums text-foreground">{value.toLocaleString()}</div>
    </div>
  )
}
