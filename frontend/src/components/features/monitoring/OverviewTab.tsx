/**
 * Overview Tab
 * High-level system health summary
 */

import {
  Activity,
  AlertTriangle,
  Clock3,
  Search,
  Tag,
  CheckCircle2,
  Map as MapIcon,
} from 'lucide-react'
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
    <div className="space-y-5">
      <div
        className={`rounded-md border p-5 ${
          isHealthy
            ? 'border-status-healthy/30 bg-status-healthy/10'
            : 'border-status-critical/30 bg-status-critical/10'
        }`}
      >
        <div className="flex items-start gap-3">
          {isHealthy ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-status-healthy" />
          ) : (
            <AlertTriangle className="mt-0.5 h-5 w-5 text-status-critical" />
          )}
          <div>
            <h2 className="text-h2 text-foreground">
              {isLoading
                ? 'Loading status...'
                : isHealthy
                  ? 'All Systems Operational'
                  : 'System Issues Detected'}
            </h2>
            <p className="mt-1 text-small text-muted-foreground">
              {isHealthy
                ? 'All services are running normally.'
                : 'Some backend services are currently degraded.'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 stagger-enter">
        <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
          <div className="mb-2 flex items-center gap-2 text-muted-foreground">
            <Clock3 className="h-4 w-4" />
            <span className="text-tiny">Uptime</span>
          </div>
          <p className="text-h2 tabular-nums text-foreground">
            {isLoading ? '—' : formatUptime(uptime)}
          </p>
        </div>

        <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
          <div className="mb-2 flex items-center gap-2 text-muted-foreground">
            <Tag className="h-4 w-4" />
            <span className="text-tiny">Version</span>
          </div>
          <p className="text-h2 tabular-nums text-foreground">{isLoading ? '—' : version}</p>
        </div>

        <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
          <div className="mb-2 flex items-center gap-2 text-muted-foreground">
            <Activity className="h-4 w-4" />
            <span className="text-tiny">Status</span>
          </div>
          <p className={`text-h2 ${isHealthy ? 'text-status-healthy' : 'text-status-critical'}`}>
            {isLoading ? '—' : isHealthy ? 'Healthy' : 'Issues'}
          </p>
        </div>
      </div>

      <div className="rounded-md border border-border bg-card p-5 shadow-surface-1">
        <h3 className="mb-3 text-small font-semibold uppercase tracking-[0.05em] text-muted-foreground">
          Quick Actions
        </h3>
        <div className="flex flex-wrap gap-2">
          <a
            href="/heatmap"
            className="btn-bvv inline-flex items-center gap-2 rounded-md border border-primary/30 bg-primary/12 px-3 py-2 text-small font-semibold text-primary hover:bg-primary/18"
          >
            <MapIcon className="h-4 w-4" />
            View Heatmap
          </a>
          <a
            href="/search"
            className="btn-bvv inline-flex items-center gap-2 rounded-md border border-primary/30 bg-primary/12 px-3 py-2 text-small font-semibold text-primary hover:bg-primary/18"
          >
            <Search className="h-4 w-4" />
            Search Stations
          </a>
        </div>
      </div>
    </div>
  )
}
