/**
 * Departures Page
 * Hosts station search and (soon) the live departures board.
 */

import { useState } from 'react'
import StationSearch from '../components/StationSearch'
import type { Station } from '../types/api'

export default function DeparturesPage() {
  const [selectedStation, setSelectedStation] = useState<Station | null>(null)

  return (
    <div className="container mx-auto p-4">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Departures</h1>
        <p className="mt-2 text-sm text-slate-600">
          Look up a station to see live departures and cache freshness indicators.
        </p>
      </header>

      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <StationSearch onSelect={station => setSelectedStation(station)} />
        {selectedStation && (
          <div className="mt-4 rounded-md border border-slate-100 bg-slate-50 p-4">
            <p className="text-sm font-medium text-slate-700">Selected station</p>
            <h2 className="text-xl font-semibold text-slate-900">{selectedStation.name}</h2>
            <p className="text-sm text-slate-600">{selectedStation.place}</p>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500">
        Live departures board coming soon.
      </section>
    </div>
  )
}
