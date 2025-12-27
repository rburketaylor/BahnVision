/**
 * Performance Tab
 * Prometheus metrics, cache performance, and response times
 * (Content migrated from original InsightsPage)
 */

import { useState, useEffect } from 'react'
import { useHealth } from '../../hooks/useHealth'
import { apiClient } from '../../services/api'

interface SystemMetrics {
  cacheHitRate: number
  avgResponseTime: number
  totalRequests: number
  errorRate: number
  cacheEvents: Record<string, number>
}

export default function PerformanceTab() {
  const { data: health, isLoading: healthLoading } = useHealth()
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchMetrics = async () => {
    setMetricsLoading(true)
    setMetricsError(null)

    try {
      const metricsText = await apiClient.getMetrics()

      const parsedMetrics: SystemMetrics = {
        cacheHitRate: 0,
        avgResponseTime: 0,
        totalRequests: 0,
        errorRate: 0,
        cacheEvents: {},
      }

      const lines = metricsText.split('\n')

      for (const line of lines) {
        if (line.startsWith('#') || line.trim() === '') continue

        const [metric, value] = line.split(' ')
        if (!metric || !value) continue

        if (metric.startsWith('bahnvision_cache_events_total')) {
          const cacheType = metric.match(/{cache="([^"]+)",event="([^"]+)"}/)
          if (cacheType) {
            const cacheName = cacheType[1]
            const event = cacheType[2]
            const key = `${cacheName}_${event}`
            parsedMetrics.cacheEvents[key] = parseInt(value) || 0
          }
        }

        if (metric.startsWith('bahnvision_transit_requests_total')) {
          parsedMetrics.totalRequests += parseInt(value) || 0
        }

        if (metric.includes('bahnvision_transit_request_seconds') && metric.includes('le="')) {
          const duration = parseFloat(value) || 0
          if (duration > 0) {
            parsedMetrics.avgResponseTime = duration * 1000
          }
        }
      }

      const hits = parsedMetrics.cacheEvents['transit_departures_hit'] || 0
      const misses = parsedMetrics.cacheEvents['transit_departures_miss'] || 0
      const total = hits + misses
      parsedMetrics.cacheHitRate = total > 0 ? (hits / total) * 100 : 0

      setMetrics(parsedMetrics)
    } catch (error) {
      setMetricsError(error instanceof Error ? error.message : 'Failed to fetch metrics')
    } finally {
      setMetricsLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()

    let interval: number
    if (autoRefresh) {
      interval = window.setInterval(fetchMetrics, 30000)
    }

    return () => {
      if (interval) window.clearInterval(interval)
    }
  }, [autoRefresh])

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-end gap-4">
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
            autoRefresh
              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
          }`}
        >
          <span className={autoRefresh ? 'animate-pulse' : ''}>●</span>
          {autoRefresh ? 'Auto-refreshing' : 'Manual refresh'}
        </button>

        <button
          onClick={fetchMetrics}
          disabled={metricsLoading}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {metricsLoading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border border-current border-t-transparent" />
              Refreshing...
            </>
          ) : (
            <>🔄 Refresh</>
          )}
        </button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">💾</span>
            <span className="text-sm font-medium text-gray-500">Cache Hit Rate</span>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-foreground">
              {metricsLoading ? '—' : (metrics?.cacheHitRate || 0).toFixed(1)}
            </span>
            <span className="text-sm text-gray-500">%</span>
          </div>
        </div>

        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">📊</span>
            <span className="text-sm font-medium text-gray-500">API Requests</span>
          </div>
          <span className="text-2xl font-bold text-foreground">
            {metricsLoading ? '—' : (metrics?.totalRequests || 0).toLocaleString()}
          </span>
        </div>

        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">⚡</span>
            <span className="text-sm font-medium text-gray-500">Response Time</span>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-foreground">
              {metricsLoading ? '—' : (metrics?.avgResponseTime || 0).toFixed(0)}
            </span>
            <span className="text-sm text-gray-500">ms</span>
          </div>
        </div>

        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">⏱️</span>
            <span className="text-sm font-medium text-gray-500">Uptime</span>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-foreground">
              {healthLoading
                ? '—'
                : health?.data?.uptime_seconds
                  ? Math.floor(health.data.uptime_seconds / 3600)
                  : '0'}
            </span>
            <span className="text-sm text-gray-500">hours</span>
          </div>
        </div>
      </div>

      {/* Detailed Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cache Performance */}
        <div className="bg-card rounded-lg border border-border p-6">
          <h2 className="text-xl font-semibold text-foreground mb-4">Cache Performance</h2>

          {metricsLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
              ))}
            </div>
          ) : metrics ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Overall Hit Rate</span>
                <span className="text-lg font-semibold text-foreground">
                  {metrics.cacheHitRate.toFixed(1)}%
                </span>
              </div>

              <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    metrics.cacheHitRate > 70
                      ? 'bg-green-500'
                      : metrics.cacheHitRate > 50
                        ? 'bg-yellow-500'
                        : 'bg-red-500'
                  }`}
                  style={{ width: `${metrics.cacheHitRate}%` }}
                />
              </div>

              <div className="space-y-2 pt-4 border-t border-border">
                <h4 className="text-sm font-medium text-foreground">Cache Events</h4>
                {Object.entries(metrics.cacheEvents)
                  .slice(0, 6)
                  .map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-gray-500">{key.replace(/_/g, ' ')}</span>
                      <span className="font-medium text-foreground">{value.toLocaleString()}</span>
                    </div>
                  ))}
              </div>
            </div>
          ) : metricsError ? (
            <div className="text-center py-4 text-red-600">
              <p className="text-sm">Failed to load metrics</p>
              <p className="text-xs mt-1">{metricsError}</p>
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500">
              <p>No metrics available</p>
            </div>
          )}
        </div>

        {/* Performance Targets */}
        <div className="bg-card rounded-lg border border-border p-6">
          <h2 className="text-xl font-semibold text-foreground mb-4">Performance Targets</h2>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-500">Cache Hit Rate Target</span>
              <span className="text-green-600 font-medium">≥ 70%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-500">Response Time Target</span>
              <span className="text-green-600 font-medium">&lt; 750ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-500">Error Rate Target</span>
              <span className="text-green-600 font-medium">&lt; 5/min</span>
            </div>

            <div className="pt-4 border-t border-border">
              <h4 className="text-sm font-medium text-foreground mb-3">Current Status</h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${(metrics?.cacheHitRate || 0) >= 70 ? 'bg-green-500' : 'bg-red-500'}`}
                  />
                  <span className="text-sm text-gray-500">
                    Cache: {(metrics?.cacheHitRate || 0) >= 70 ? 'Meeting target' : 'Below target'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${(metrics?.avgResponseTime || 0) < 750 ? 'bg-green-500' : 'bg-red-500'}`}
                  />
                  <span className="text-sm text-gray-500">
                    Response:{' '}
                    {(metrics?.avgResponseTime || 0) < 750 ? 'Meeting target' : 'Above target'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-sm text-gray-500">
        <p>Last updated: {new Date().toLocaleString()}</p>
        {autoRefresh && <p className="mt-1">Auto-refreshing every 30 seconds</p>}
      </div>
    </div>
  )
}
