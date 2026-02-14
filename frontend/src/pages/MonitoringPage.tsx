/**
 * Monitoring Page
 * Tabbed system monitoring with Overview, Ingestion, and Performance sections
 */

import { useState } from 'react'
import { Activity, Gauge, Inbox } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Avatar, AvatarFallback } from '../components/ui/avatar'
import OverviewTab from '../components/features/monitoring/OverviewTab'
import IngestionTab from '../components/features/monitoring/IngestionTab'
import PerformanceTab from '../components/features/monitoring/PerformanceTab'

export default function MonitoringPage() {
  const [activeTab, setActiveTab] = useState('overview')

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Card className="overflow-hidden border-border/80 shadow-surface-1">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14 bg-status-info/10">
              <AvatarFallback className="bg-status-info/10 text-status-info">
                <Activity className="h-7 w-7" />
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-tiny text-muted-foreground">Operations Control</p>
              <CardTitle className="text-h1 text-foreground">System Monitoring</CardTitle>
              <p className="mt-1 text-body text-muted-foreground">
                Real-time health, ingestion status, and performance metrics.
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mt-2 h-auto flex-wrap gap-1 bg-transparent p-0">
              <TabsTrigger value="overview" className="gap-2 data-[state=active]:bg-primary/12">
                <Activity className="h-4 w-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="ingestion" className="gap-2 data-[state=active]:bg-primary/12">
                <Inbox className="h-4 w-4" />
                Ingestion
              </TabsTrigger>
              <TabsTrigger value="performance" className="gap-2 data-[state=active]:bg-primary/12">
                <Gauge className="h-4 w-4" />
                Performance
              </TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="mt-6">
              <OverviewTab />
            </TabsContent>
            <TabsContent value="ingestion" className="mt-6">
              <IngestionTab />
            </TabsContent>
            <TabsContent value="performance" className="mt-6">
              <PerformanceTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
