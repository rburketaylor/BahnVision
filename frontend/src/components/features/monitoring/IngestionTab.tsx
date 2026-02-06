/**
 * Ingestion Tab
 * GTFS data pipeline status (static feed + realtime harvester)
 */

import { useState } from 'react'
import { apiClient } from '../../../services/api'
import { useAutoRefresh } from '../../../hooks/useAutoRefresh'
import type { IngestionStatus } from '../../../types/ingestion'
import { ErrorCard, RefreshButton } from '../../shared'

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
    return new Date(dateStr).toLocaleString()
  }

  const formatShortDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString()
  }

  if (error) {
    return (
      <ErrorCard title="Failed to load ingestion status" message={error} onRetry={fetchStatus} />
    )
  }

  return (
    <div className="space-y-6">
      {/* Refresh Button */}
      <div className="flex justify-end">
        <RefreshButton onClick={fetchStatus} loading={loading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* GTFS Static Feed Card */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📦</span>
            <h2 className="text-xl font-semibold text-foreground">GTFS Static Feed</h2>
          </div>

          {loading && !status ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
              ))}
            </div>
          ) : status?.gtfs_feed ? (
            <div className="space-y-4">
              {/* Status Indicator */}
              <div className="flex items-center gap-2">
                <span
                  className={`w-3 h-3 rounded-full ${
                    status.gtfs_feed.is_expired
                      ? 'bg-red-500'
                      : status.gtfs_feed.feed_id
                        ? 'bg-green-500'
                        : 'bg-gray-400'
                  }`}
                />
                <span className="text-sm font-medium text-foreground">
                  {status.gtfs_feed.is_expired
                    ? 'Feed Expired'
                    : status.gtfs_feed.feed_id
                      ? 'Feed Active'
                      : 'No Feed Loaded'}
                </span>
              </div>

              {/* Feed Details */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Last Import</span>
                  <span className="text-foreground font-medium">
                    {formatDate(status.gtfs_feed.downloaded_at)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Valid From</span>
                  <span className="text-foreground">
                    {formatShortDate(status.gtfs_feed.feed_start_date)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Valid Until</span>
                  <span
                    className={
                      status.gtfs_feed.is_expired ? 'text-red-600 font-medium' : 'text-foreground'
                    }
                  >
                    {formatShortDate(status.gtfs_feed.feed_end_date)}
                  </span>
                </div>
              </div>

              {/* Record Counts */}
              <div className="pt-4 border-t border-border">
                <h4 className="text-sm font-medium text-foreground mb-3">Record Counts</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-lg font-bold text-foreground">
                      {status.gtfs_feed.stop_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">Stops</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-lg font-bold text-foreground">
                      {status.gtfs_feed.route_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">Routes</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-lg font-bold text-foreground">
                      {status.gtfs_feed.trip_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">Trips</div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No feed data available</p>
          )}
        </div>

        {/* GTFS-RT Harvester Card */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📡</span>
            <h2 className="text-xl font-semibold text-foreground">Realtime Harvester</h2>
          </div>

          {loading && !status ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
              ))}
            </div>
          ) : status?.gtfs_rt_harvester ? (
            <div className="space-y-4">
              {/* Status Indicator */}
              <div className="flex items-center gap-2">
                <span
                  className={`w-3 h-3 rounded-full ${
                    status.gtfs_rt_harvester.is_running
                      ? 'bg-green-500 animate-pulse'
                      : 'bg-gray-400'
                  }`}
                />
                <span className="text-sm font-medium text-foreground">
                  {status.gtfs_rt_harvester.is_running ? 'Running' : 'Stopped'}
                </span>
              </div>

              {/* Harvester Details */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Last Harvest</span>
                  <span className="text-foreground">
                    {status.gtfs_rt_harvester.last_harvest_at
                      ? formatDate(status.gtfs_rt_harvester.last_harvest_at)
                      : 'Never'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Stations Updated (Last)</span>
                  <span className="text-foreground font-medium">
                    {status.gtfs_rt_harvester.stations_updated_last_harvest.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Stats Records</span>
                  <span className="text-foreground font-medium">
                    {status.gtfs_rt_harvester.total_stats_records.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Visual Stats */}
              <div className="pt-4 border-t border-border">
                <div className="flex items-center gap-3">
                  <div
                    className={`flex-1 h-2 rounded-full ${
                      status.gtfs_rt_harvester.is_running ? 'bg-green-100' : 'bg-gray-100'
                    }`}
                  >
                    <div
                      className={`h-2 rounded-full transition-all ${
                        status.gtfs_rt_harvester.is_running
                          ? 'bg-green-500 animate-pulse'
                          : 'bg-gray-400'
                      }`}
                      style={{
                        width: status.gtfs_rt_harvester.is_running ? '100%' : '0%',
                      }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">
                    {status.gtfs_rt_harvester.is_running ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No harvester data available</p>
          )}
        </div>
      </div>

      {/* Info Footer */}
      <div className="text-center text-sm text-gray-500">
        <p>Data refreshes automatically every 30 seconds</p>
        <p className="mt-1">Last updated: {new Date().toLocaleTimeString()}</p>
      </div>
    </div>
  )
}
