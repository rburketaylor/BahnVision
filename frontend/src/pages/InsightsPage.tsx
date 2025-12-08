/**
 * Insights Page
 * System health metrics and analytics
 */

import { useState, useEffect } from 'react'
import { useHealth } from '../hooks/useHealth'
import { apiClient } from '../services/api'

interface SystemMetrics {
  cacheHitRate: number
  avgResponseTime: number
  totalRequests: number
  errorRate: number
  cacheEvents: Record<string, number>
}

interface MetricCard {
  title: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'stable'
  description?: string
  icon?: string
}

export default function InsightsPage() {
  const { data: health, isLoading: healthLoading, error: healthError } = useHealth()
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Fetch Prometheus metrics
  const fetchMetrics = async () => {
    setMetricsLoading(true)
    setMetricsError(null)

    try {
      const metricsText = await apiClient.getMetrics()

      // Parse Prometheus metrics
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

        // Parse cache events
        if (metric.startsWith('bahnvision_cache_events_total')) {
          const cacheType = metric.match('{cache="([^"]+)",event="([^"]+)"}')
          if (cacheType) {
            const cacheName = cacheType[1]
            const event = cacheType[2]
            const key = `${cacheName}_${event}`
            parsedMetrics.cacheEvents[key] = parseInt(value) || 0
          }
        }

        // Parse request metrics
        if (metric.startsWith('bahnvision_transit_requests_total')) {
          parsedMetrics.totalRequests += parseInt(value) || 0
        }

        // Parse response time metrics
        if (metric.includes('bahnvision_transit_request_seconds') && metric.includes('le="')) {
          // This is a histogram - simplified parsing for demo
          const duration = parseFloat(value) || 0
          if (duration > 0) {
            parsedMetrics.avgResponseTime = duration * 1000 // Convert to milliseconds
          }
        }
      }

      // Calculate cache hit rate
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
      interval = window.setInterval(fetchMetrics, 30000) // Refresh every 30 seconds
    }

    return () => {
      if (interval) window.clearInterval(interval)
    }
  }, [autoRefresh])

  // Prepare metric cards
  const metricCards: MetricCard[] = [
    {
      title: 'System Status',
      value: health?.data?.status === 'ok' ? 'Healthy' : 'Issues',
      icon: health?.data?.status === 'ok' ? '🟢' : '🔴',
      description:
        health?.data?.status === 'ok' ? 'All systems operational' : 'Some systems may be degraded',
      trend: 'stable',
    },
    {
      title: 'Cache Hit Rate',
      value: (metrics?.cacheHitRate || 0).toFixed(1),
      unit: '%',
      icon: '💾',
      description: 'Percentage of cache hits vs misses',
      trend:
        (metrics?.cacheHitRate || 0) > 70
          ? 'up'
          : (metrics?.cacheHitRate || 0) < 50
            ? 'down'
            : 'stable',
    },
    {
      title: 'API Requests',
      value: (metrics?.totalRequests || 0).toLocaleString(),
      icon: '📊',
      description: 'Total requests processed',
      trend: 'up',
    },
    {
      title: 'Response Time',
      value: (metrics?.avgResponseTime || 0).toFixed(0),
      unit: 'ms',
      icon: '⚡',
      description: 'Average API response time',
      trend: (metrics?.avgResponseTime || 0) < 750 ? 'up' : 'down',
    },
    {
      title: 'Uptime',
      value: health?.data?.uptime_seconds ? Math.floor(health?.data?.uptime_seconds / 3600) : '0',
      unit: 'hours',
      icon: '⏱️',
      description: 'System uptime',
      trend: 'stable',
    },
    {
      title: 'Version',
      value: health?.data?.version || 'Unknown',
      icon: '🏷️',
      description: 'Application version',
      trend: 'stable',
    },
  ]

  const getTrendColor = (trend?: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up':
        return 'text-green-600'
      case 'down':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  const getTrendIcon = (trend?: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up':
        return '↑'
      case 'down':
        return '↓'
      default:
        return '→'
    }
  }

  if (healthError) {
    return (
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground">System Insights</h1>
          <p className="text-gray-400 mt-2">Real-time system health and performance metrics</p>
        </header>

        <div className="bg-red-50 border border-red-200 text-red-800 p-6 rounded-lg">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🚨</span>
            <div>
              <h3 className="font-semibold">Failed to load system health</h3>
              <p className="text-sm mt-1">
                {typeof healthError === 'string' ? healthError : 'Unknown error occurred'}
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground">System Insights</h1>
            <p className="text-gray-400 mt-2">Real-time system health and performance metrics</p>
          </div>

          <div className="flex items-center gap-4">
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
                  <span className="h-4 w-4 animate-spin rounded-full border border-current border-t-transparent"></span>
                  Refreshing...
                </>
              ) : (
                <>🔄 Refresh</>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {metricCards.map((card, index) => (
          <div
            key={index}
            className="bg-card rounded-lg border border-border p-6 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="text-2xl">{card.icon}</div>
              {card.trend && (
                <span className={`text-sm font-medium ${getTrendColor(card.trend)}`}>
                  {getTrendIcon(card.trend)}
                </span>
              )}
            </div>

            <div className="space-y-1">
              <h3 className="text-sm font-medium text-gray-500">{card.title}</h3>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold text-foreground">
                  {healthLoading && index === 0 ? (
                    <span className="h-6 w-12 bg-gray-200 animate-pulse rounded"></span>
                  ) : (
                    card.value
                  )}
                </span>
                {card.unit && <span className="text-sm text-gray-500">{card.unit}</span>}
              </div>
              {card.description && <p className="text-xs text-gray-400 mt-1">{card.description}</p>}
            </div>
          </div>
        ))}
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Cache Performance */}
        <div className="bg-card rounded-lg border border-border p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-foreground mb-4">Cache Performance</h2>

          {metricsLoading ? (
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
            </div>
          ) : metrics ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Overall Hit Rate</span>
                <span className="text-lg font-semibold text-foreground">
                  {metrics.cacheHitRate.toFixed(1)}%
                </span>
              </div>

              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    metrics.cacheHitRate > 70
                      ? 'bg-green-500'
                      : metrics.cacheHitRate > 50
                        ? 'bg-yellow-500'
                        : 'bg-red-500'
                  }`}
                  style={{ width: `${metrics.cacheHitRate}%` }}
                ></div>
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

        {/* System Information */}
        <div className="bg-card rounded-lg border border-border p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-foreground mb-4">System Information</h2>

          {healthLoading ? (
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
              <div className="h-4 bg-gray-200 animate-pulse rounded"></div>
            </div>
          ) : health ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Status</span>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    health?.data?.status === 'ok'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                  }`}
                >
                  {health?.data?.status === 'ok' ? '🟢 Healthy' : '🔴 Issues'}
                </span>
              </div>

              {health?.data?.version && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Version</span>
                  <span className="font-mono text-sm text-foreground">{health?.data?.version}</span>
                </div>
              )}

              {health?.data?.uptime_seconds && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Uptime</span>
                  <span className="text-sm text-foreground">
                    {Math.floor(health?.data?.uptime_seconds / 86400)}d{' '}
                    {Math.floor((health?.data?.uptime_seconds % 86400) / 3600)}h{' '}
                    {Math.floor((health?.data?.uptime_seconds % 3600) / 60)}m
                  </span>
                </div>
              )}

              <div className="pt-4 border-t border-border">
                <h4 className="text-sm font-medium text-foreground mb-2">Performance Targets</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Cache Hit Rate Target</span>
                    <span className="text-green-600">≥ 70%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Response Time Target</span>
                    <span className="text-green-600">&lt; 750ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Error Rate Target</span>
                    <span className="text-green-600">&lt; 5/min</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500">
              <p>No health information available</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-8 text-center text-sm text-gray-500">
        <p>Last updated: {new Date().toLocaleString()}</p>
        {autoRefresh && <p className="mt-1">Auto-refreshing every 30 seconds</p>}
      </div>
    </div>
  )
}
