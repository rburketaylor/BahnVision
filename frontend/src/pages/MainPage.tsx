import { useNavigate } from 'react-router'
import { ArrowRight, Clock3, Map, Radar, Search, TrainFront } from 'lucide-react'
import { StationSearch } from '../components/features/station/StationSearch'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Separator } from '../components/ui/separator'
import { Avatar, AvatarFallback } from '../components/ui/avatar'
import type { TransitStop } from '../types/gtfs'

const capabilities = [
  {
    icon: TrainFront,
    title: 'Live Departures',
    description: 'Station boards with delay and cancellation state.',
    color: 'bg-primary/10 text-primary',
  },
  {
    icon: Clock3,
    title: 'Trend Analysis',
    description: 'Historical station reliability by time window.',
    color: 'bg-status-info/10 text-status-info',
  },
  {
    icon: Radar,
    title: 'Operations Visibility',
    description: 'Monitoring dashboards for data pipeline and API health.',
    color: 'bg-status-healthy/10 text-status-healthy',
  },
]

export function MainPage() {
  const navigate = useNavigate()

  const handleStationSelect = (stop: TransitStop) => {
    navigate(`/station/${stop.id}`)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-10rem)] w-full max-w-5xl flex-col gap-8">
      <section className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card className="overflow-hidden border-border/80 shadow-surface-1">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <Avatar className="h-10 w-10 bg-primary/10">
                <AvatarFallback className="bg-primary/10 text-primary">
                  <Search className="h-5 w-5" />
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-tiny text-muted-foreground">Station Operations</p>
                <CardTitle className="text-h1 text-foreground">Command Search</CardTitle>
              </div>
            </div>
            <p className="mt-2 text-body text-muted-foreground">
              Query any stop in the German network and jump directly into live station operations.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-border bg-surface-elevated p-2">
              <StationSearch
                onSelect={handleStationSelect}
                placeholder="Search station name or stop ID..."
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5">
                <Search className="h-3 w-3" />
                Instant lookup
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5">
                <Clock3 className="h-3 w-3" />
                Live data
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-border/80 shadow-surface-1">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <Avatar className="h-10 w-10 bg-status-info/10">
                <AvatarFallback className="bg-status-info/10 text-status-info">
                  <Map className="h-5 w-5" />
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-tiny text-muted-foreground">Network Access</p>
                <CardTitle className="text-h2">Quick Routes</CardTitle>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button className="w-full justify-between" size="lg" onClick={() => navigate('/')}>
              Network Heatmap
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              variant="secondary"
              className="w-full justify-between"
              size="lg"
              onClick={() => navigate('/monitoring')}
            >
              System Monitoring
              <Radar className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </section>

      <Separator className="my-2" />

      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <h2 className="text-h2 text-foreground">Capabilities</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {capabilities.map((cap, idx) => {
            const Icon = cap.icon
            return (
              <Card
                key={idx}
                className="group overflow-hidden border-border/60 transition-all duration-200 hover:border-primary/30 hover:shadow-md"
              >
                <CardContent className="flex items-start gap-4 p-5">
                  <div className={`rounded-lg p-2.5 ${cap.color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="space-y-1.5">
                    <p className="font-semibold text-foreground">{cap.title}</p>
                    <p className="text-small text-muted-foreground leading-relaxed">
                      {cap.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>
    </div>
  )
}
