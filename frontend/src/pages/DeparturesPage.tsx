import { useState } from 'react'
import { useParams } from 'react-router'
import { useDepartures } from '../hooks/useDepartures'
import { DeparturesBoard } from '../components/DeparturesBoard'
import type { TransportType } from '../types/api'

const ALL_TRANSPORT_TYPES: TransportType[] = ['BAHN', 'SBAHN', 'UBAHN', 'TRAM', 'BUS', 'REGIONAL_BUS', 'SEV', 'SCHIFF']

export function DeparturesPage() {
  const { stationId } = useParams<{ stationId: string }>()
  const [selectedTransportTypes, setSelectedTransportTypes] = useState<TransportType[]>([])

  const { data: apiResponse, isLoading, error } = useDepartures(
    { station: stationId!, transport_type: selectedTransportTypes },
    !!stationId
  )

  const { station, departures } = apiResponse?.data || {}

  const toggleTransportType = (transportType: TransportType) => {
    setSelectedTransportTypes((prev) =>
      prev.includes(transportType) ? prev.filter((t) => t !== transportType) : [...prev, transportType]
    )
  }

  return (
    <div className="space-y-8">
      <header>
        {stationId && <h1 className="text-4xl font-bold text-foreground">Departures for {station?.name}</h1>}
      </header>

      <div className="rounded-lg border border-border bg-card p-4 shadow-md">
        <div className="mb-4 flex flex-wrap gap-2">
          {ALL_TRANSPORT_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => toggleTransportType(type)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                selectedTransportTypes.includes(type)
                  ? 'bg-gray-900 text-white border border-gray-900 shadow-sm'
                  : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-100'
              }`}
            >
              {type === 'REGIONAL_BUS' ? 'REGIONAL BUS' : type}
            </button>
          ))}
        </div>
      </div>

      <section className="rounded-lg border border-border bg-card p-6 shadow-lg">
        {isLoading && <p className="text-center text-gray-400">Loading departures...</p>}
        {error && <p className="text-center text-red-500">Error fetching departures: {error.message}</p>}
        {departures && <DeparturesBoard departures={departures} />}
      </section>
    </div>
  )
}
