import { useNavigate } from 'react-router'
import { StationSearch } from '../components/StationSearch'
import type { Station } from '../types/api'

export function MainPage() {
  const navigate = useNavigate()

  const handleStationSelect = (station: Station) => {
    navigate(`/departures/${station.id}`)
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero Section */}
      <div className="flex-1 flex items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div className="max-w-4xl w-full space-y-8 text-center">
          <header className="space-y-4">
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground tracking-tight">
              BahnVision
            </h1>
            <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto">
              Your real-time companion for Munich public transport.
            </p>
          </header>

          <section className="max-w-2xl mx-auto w-full">
            <div className="rounded-xl border border-border bg-card p-6 sm:p-8 shadow-xl backdrop-blur-sm bg-opacity-95">
              <div className="space-y-4">
                <h2 className="text-2xl font-semibold text-foreground">Search for a Station</h2>
                <StationSearch onSelect={handleStationSelect} />
              </div>
            </div>
          </section>

          {/* Quick Links */}
          <section className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-8">
            <div className="p-6 rounded-lg bg-card border border-border">
              <h3 className="text-lg font-semibold text-primary mb-2">Real-time Data</h3>
              <p className="text-sm text-gray-400">
                Live departure information with delay indicators
              </p>
            </div>
            <div className="p-6 rounded-lg bg-card border border-border">
              <h3 className="text-lg font-semibold text-primary mb-2">Route Planning</h3>
              <p className="text-sm text-gray-400">
                Plan your journey across Munich's transit network
              </p>
            </div>
            <div className="p-6 rounded-lg bg-card border border-border">
              <h3 className="text-lg font-semibold text-primary mb-2">System Insights</h3>
              <p className="text-sm text-gray-400">Monitor system performance and statistics</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
