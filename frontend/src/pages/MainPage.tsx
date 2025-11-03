import { useNavigate } from 'react-router'
import { StationSearch } from '../components/StationSearch'
import type { Station } from '../types/api'

export function MainPage() {
  const navigate = useNavigate()

  const handleStationSelect = (station: Station) => {
    navigate(`/departures/${station.id}`)
  }

  return (
    <div className="space-y-8">
      <header className="text-center">
        <h1 className="text-5xl font-bold text-foreground">BahnVision</h1>
        <p className="mt-4 text-xl text-gray-400">
          Your real-time companion for Munich public transport.
        </p>
      </header>

      <section className="mx-auto max-w-2xl rounded-lg border border-border bg-card p-8 shadow-lg">
        <StationSearch onSelect={handleStationSelect} />
      </section>
    </div>
  )
}
