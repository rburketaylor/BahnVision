/**
 * Monitoring Page
 * Tabbed system monitoring with Overview, Ingestion, and Performance sections
 */

import { useState, type ComponentType } from 'react'
import { Activity, Gauge, Inbox } from 'lucide-react'
import OverviewTab from '../components/features/monitoring/OverviewTab'
import IngestionTab from '../components/features/monitoring/IngestionTab'
import PerformanceTab from '../components/features/monitoring/PerformanceTab'

type TabId = 'overview' | 'ingestion' | 'performance'

interface Tab {
  id: TabId
  label: string
  icon: ComponentType<{ className?: string }>
}

const tabs: Tab[] = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'ingestion', label: 'Ingestion', icon: Inbox },
  { id: 'performance', label: 'Performance', icon: Gauge },
]

export default function MonitoringPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="rounded-lg border border-border bg-card p-5 shadow-surface-1">
        <p className="text-tiny text-muted-foreground">Operations Control</p>
        <h1 className="text-h1 text-foreground">System Monitoring</h1>
        <p className="mt-1 text-body text-muted-foreground">
          Real-time health, ingestion status, and performance metrics.
        </p>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Monitoring tabs">
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`btn-bvv inline-flex items-center gap-2 rounded-md border px-3 py-2 text-small font-semibold uppercase tracking-[0.05em] transition-colors ${
                isActive
                  ? 'border-primary/40 bg-primary/12 text-primary shadow-surface-1'
                  : 'border-border bg-surface text-muted-foreground hover:bg-surface-elevated hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </nav>

      <div className="animate-content-fade">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'ingestion' && <IngestionTab />}
        {activeTab === 'performance' && <PerformanceTab />}
      </div>
    </div>
  )
}
