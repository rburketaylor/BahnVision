/**
 * Monitoring Page
 * Tabbed system monitoring with Overview, Ingestion, and Performance sections
 */

import { useState } from 'react'
import OverviewTab from '../components/monitoring/OverviewTab'
import IngestionTab from '../components/monitoring/IngestionTab'
import PerformanceTab from '../components/monitoring/PerformanceTab'

type TabId = 'overview' | 'ingestion' | 'performance'

interface Tab {
  id: TabId
  label: string
  icon: string
}

const tabs: Tab[] = [
  { id: 'overview', label: 'Overview', icon: '📊' },
  { id: 'ingestion', label: 'Ingestion', icon: '📥' },
  { id: 'performance', label: 'Performance', icon: '⚡' },
]

export default function MonitoringPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground">System Monitoring</h1>
        <p className="text-gray-400 mt-2">
          Real-time system health, data ingestion, and performance metrics
        </p>
      </header>

      {/* Tab Navigation */}
      <nav className="flex gap-1 mb-8 border-b border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-3 font-medium text-sm transition-colors relative flex items-center gap-2 ${
              activeTab === tab.id
                ? 'text-primary border-b-2 border-primary -mb-[2px]'
                : 'text-gray-500 hover:text-foreground'
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'ingestion' && <IngestionTab />}
        {activeTab === 'performance' && <PerformanceTab />}
      </div>
    </div>
  )
}
