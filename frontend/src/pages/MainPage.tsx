import { useNavigate } from 'react-router'
import { ArrowRight, Clock3, Radar, Search as SearchIcon } from 'lucide-react'
import { StationSearch } from '../components/features/station/StationSearch'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import type { TransitStop } from '../types/gtfs'

export function MainPage() {
  const navigate = useNavigate()

  const handleStationSelect = (stop: TransitStop) => {
    navigate(`/station/${stop.id}`)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-10rem)] w-full max-w-6xl flex-col gap-6">
      <section className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Card className="border-border/90 bg-card/95 animate-panel-enter">
          <CardHeader className="border-b border-border/70 pb-4">
            <p className="text-tiny text-muted-foreground">Station Operations</p>
            <CardTitle className="text-display text-foreground">Command Search</CardTitle>
            <p className="max-w-2xl text-body text-muted-foreground">
              Query any stop in the German network and jump directly into live station operations.
            </p>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="rounded-md border border-border bg-surface-elevated p-3">
              <StationSearch
                onSelect={handleStationSelect}
                placeholder="Search station name or stop ID"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 text-small text-muted-foreground">
              <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5">
                <SearchIcon className="h-3.5 w-3.5" />
                Instant station lookup
              </span>
              <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5">
                <Clock3 className="h-3.5 w-3.5" />
                Live departures and trends
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/90 bg-card/95 animate-panel-enter">
          <CardHeader className="pb-3">
            <p className="text-tiny text-muted-foreground">Network Access</p>
            <CardTitle className="text-h1">Quick Routes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <Button className="w-full justify-between" onClick={() => navigate('/')}>
              Open Network Heatmap
              <ArrowRight />
            </Button>
            <Button
              variant="secondary"
              className="w-full justify-between"
              onClick={() => navigate('/monitoring')}
            >
              Open System Monitoring
              <Radar className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 sm:grid-cols-3 stagger-enter">
        <Card>
          <CardContent className="space-y-2 p-4">
            <p className="text-tiny text-muted-foreground">Capability</p>
            <p className="text-h3 text-foreground">Live Departures</p>
            <p className="text-small text-muted-foreground">
              Station boards with delay and cancellation state.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-2 p-4">
            <p className="text-tiny text-muted-foreground">Capability</p>
            <p className="text-h3 text-foreground">Trend Analysis</p>
            <p className="text-small text-muted-foreground">
              Historical station reliability by time window.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-2 p-4">
            <p className="text-tiny text-muted-foreground">Capability</p>
            <p className="text-h3 text-foreground">Operations Visibility</p>
            <p className="text-small text-muted-foreground">
              Monitoring dashboards for data pipeline and API health.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
