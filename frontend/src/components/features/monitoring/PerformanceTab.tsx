/**
 * Performance Tab
 * Prometheus metrics, cache performance, and response times
 */

import { useState, type ReactNode } from 'react'
import { CheckCircle2, Clock3, Database, Gauge, Server, XCircle } from 'lucide-react'
import { useHealth } from '../../../hooks/useHealth'
import { useAutoRefresh } from '../../../hooks/useAutoRefresh'
import { apiClient } from '../../../services/api'
import { RefreshButton } from '../../shared'

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
      let responseTimeSumSeconds = 0
      let responseTimeCount = 0

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

        if (metric.startsWith('bahnvision_transit_request_seconds_sum')) {
          responseTimeSumSeconds += parseFloat(value) || 0
        }

        if (metric.startsWith('bahnvision_transit_request_seconds_count')) {
          responseTimeCount += parseFloat(value) || 0
        }
      }

      const hits = parsedMetrics.cacheEvents['json_hit'] || 0
      const misses = parsedMetrics.cacheEvents['json_miss'] || 0
      const total = hits + misses
      parsedMetrics.cacheHitRate = total > 0 ? (hits / total) * 100 : 0
      parsedMetrics.avgResponseTime =
        responseTimeCount > 0 ? (responseTimeSumSeconds / responseTimeCount) * 1000 : 0

      setMetrics(parsedMetrics)
    } catch (error) {
      setMetricsError(error instanceof Error ? error.message : 'Failed to fetch metrics')
    } finally {
      setMetricsLoading(false)
    }
  }

  useAutoRefresh({ callback: fetchMetrics, enabled: autoRefresh, runOnMount: true })

  const cacheTargetMet = (metrics?.cacheHitRate || 0) >= 70
  const responseTargetMet = (metrics?.avgResponseTime || 0) < 750

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-2 text-small font-semibold uppercase tracking-[0.05em] ${
            autoRefresh
              ? 'border-status-healthy/35 bg-status-healthy/12 text-status-healthy'
              : 'border-border bg-surface-elevated text-muted-foreground'
          }`}
        >
          <span
            className={`h-2.5 w-2.5 rounded-full ${autoRefresh ? 'bg-status-healthy animate-status-pulse' : 'bg-status-neutral'}`}
          />
          {autoRefresh ? 'Auto-refreshing' : 'Manual refresh'}
        </button>

        <RefreshButton onClick={fetchMetrics} loading={metricsLoading} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger-enter">
        <MetricCard
          icon={<Database className="h-4 w-4" />}
          label="Cache Hit Rate"
          value={metricsLoading ? '—' : `${(metrics?.cacheHitRate || 0).toFixed(1)}%`}
        />
        <MetricCard
          icon={<Server className="h-4 w-4" />}
          label="API Requests"
          value={metricsLoading ? '—' : (metrics?.totalRequests || 0).toLocaleString()}
        />
        <MetricCard
          icon={<Gauge className="h-4 w-4" />}
          label="Response Time"
          value={metricsLoading ? '—' : `${(metrics?.avgResponseTime || 0).toFixed(0)} ms`}
        />
        <MetricCard
          icon={<Clock3 className="h-4 w-4" />}
          label="Uptime"
          value={
            healthLoading
              ? '—'
              : `${health?.data?.uptime_seconds ? Math.floor(health.data.uptime_seconds / 3600) : 0} hours`
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-card p-5 shadow-surface-1">
          <h2 className="mb-4 text-h2 text-foreground">Cache Performance</h2>

          {metricsLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-surface-muted" />
              ))}
            </div>
          ) : metrics ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-small text-muted-foreground">Overall Hit Rate</span>
                <span className="text-h2 tabular-nums text-foreground">
                  {metrics.cacheHitRate.toFixed(1)}%
                </span>
              </div>

              <div className="h-2 w-full overflow-hidden rounded bg-surface-muted">
                <div
                  className={`h-full transition-all duration-300 ${
                    metrics.cacheHitRate > 70
                      ? 'bg-status-healthy'
                      : metrics.cacheHitRate > 50
                        ? 'bg-status-warning'
                        : 'bg-status-critical'
                  }`}
                  style={{ width: `${metrics.cacheHitRate}%` }}
                />
              </div>

              <div className="space-y-2 border-t border-border pt-4">
                <h4 className="text-tiny text-muted-foreground">Cache Events</h4>
                {Object.entries(metrics.cacheEvents)
                  .slice(0, 6)
                  .map(([key, value]) => (
                    <div key={key} className="flex justify-between text-small">
                      <span className="text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                      <span className="tabular-nums text-foreground">{value.toLocaleString()}</span>
                    </div>
                  ))}
              </div>
            </div>
          ) : metricsError ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-small text-destructive">
              <p>Failed to load metrics.</p>
              <p className="mt-1 text-destructive/80">{metricsError}</p>
            </div>
          ) : (
            <p className="text-small text-muted-foreground">No metrics available.</p>
          )}
        </div>

        <div className="rounded-md border border-border bg-card p-5 shadow-surface-1">
          <h2 className="mb-4 text-h2 text-foreground">Performance Targets</h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between text-small">
              <span className="text-muted-foreground">Cache Hit Rate Target</span>
              <span className="font-semibold text-status-healthy">≥ 70%</span>
            </div>
            <div className="flex items-center justify-between text-small">
              <span className="text-muted-foreground">Response Time Target</span>
              <span className="font-semibold text-status-healthy">&lt; 750ms</span>
            </div>
            <div className="flex items-center justify-between text-small">
              <span className="text-muted-foreground">Error Rate Target</span>
              <span className="font-semibold text-status-healthy">&lt; 5/min</span>
            </div>

            <div className="border-t border-border pt-4">
              <h4 className="mb-2 text-tiny text-muted-foreground">Current Status</h4>
              <div className="space-y-2">
                <StatusLine
                  ok={cacheTargetMet}
                  label={`Cache: ${cacheTargetMet ? 'Meeting target' : 'Below target'}`}
                />
                <StatusLine
                  ok={responseTargetMet}
                  label={`Response: ${responseTargetMet ? 'Meeting target' : 'Above target'}`}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="text-center text-small text-muted-foreground">
        <p className="tabular-nums">Last updated: {new Date().toLocaleString()}</p>
        {autoRefresh && <p className="mt-1">Auto-refreshing every 30 seconds.</p>}
      </div>
    </div>
  )
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4 shadow-surface-1">
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-tiny">{label}</span>
      </div>
      <span className="text-h2 tabular-nums text-foreground">{value}</span>
    </div>
  )
}

function StatusLine({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-small">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 text-status-healthy" />
      ) : (
        <XCircle className="h-4 w-4 text-status-critical" />
      )}
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
