/**
 * Overview Tab
 * High-level system health summary
 */

import { useHealth } from '../../../hooks/useHealth'
import { ErrorCard } from '../../shared'

export default function OverviewTab() {
  const { data: health, isLoading, error } = useHealth()

  if (error) {
    return (
      <ErrorCard
        title="Failed to load system health"
        message={typeof error === 'string' ? error : 'Unknown error occurred'}
      />
    )
  }

  const isHealthy = health?.data?.status === 'ok'
  const uptime = health?.data?.uptime_seconds || 0
  const version = health?.data?.version || 'Unknown'

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${days}d ${hours}h ${minutes}m`
  }

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div
        className={`p-6 rounded-lg border ${
          isHealthy
            ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
            : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
        }`}
      >
        <div className="flex items-center gap-4">
          <span className="text-4xl">{isHealthy ? '🟢' : '🔴'}</span>
          <div>
            <h2 className="text-2xl font-bold text-foreground">
              {isLoading ? (
                <span className="h-6 w-24 bg-gray-200 animate-pulse rounded inline-block" />
              ) : isHealthy ? (
                'All Systems Operational'
              ) : (
                'System Issues Detected'
              )}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {isHealthy
                ? 'All services are running normally'
                : 'Some services may be experiencing issues'}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xl">⏱️</span>
            <span className="text-sm font-medium text-gray-500">Uptime</span>
          </div>
          <p className="text-2xl font-bold text-foreground">
            {isLoading ? (
              <span className="h-6 w-20 bg-gray-200 animate-pulse rounded inline-block" />
            ) : (
              formatUptime(uptime)
            )}
          </p>
        </div>

        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xl">🏷️</span>
            <span className="text-sm font-medium text-gray-500">Version</span>
          </div>
          <p className="text-2xl font-bold text-foreground font-mono">
            {isLoading ? (
              <span className="h-6 w-16 bg-gray-200 animate-pulse rounded inline-block" />
            ) : (
              version
            )}
          </p>
        </div>

        <div className="bg-card rounded-lg border border-border p-5">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xl">📡</span>
            <span className="text-sm font-medium text-gray-500">Status</span>
          </div>
          <p className="text-2xl font-bold text-foreground">
            {isLoading ? (
              <span className="h-6 w-16 bg-gray-200 animate-pulse rounded inline-block" />
            ) : (
              <span className={isHealthy ? 'text-green-600' : 'text-red-600'}>
                {isHealthy ? 'Healthy' : 'Issues'}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Quick Links */}
      <div className="bg-card rounded-lg border border-border p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <a
            href="/heatmap"
            className="px-4 py-2 bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors"
          >
            🗺️ View Heatmap
          </a>
          <a
            href="/search"
            className="px-4 py-2 bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors"
          >
            🔍 Search Stations
          </a>
        </div>
      </div>
    </div>
  )
}
