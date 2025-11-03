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
    <div className="container mx-auto px-4 py-8">
      {stationId && <h1 className="text-2xl font-bold mb-4">Departures for {station?.name}</h1>}

      <div className="mb-4 flex flex-wrap gap-2">
        {ALL_TRANSPORT_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => toggleTransportType(type)}
            className={`px-3 py-1 text-sm font-medium rounded-full ${
              selectedTransportTypes.includes(type)
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700'
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {isLoading && <p>Loading departures...</p>}
      {error && <p className="text-red-500">Error fetching departures: {error.message}</p>}
      {departures && <DeparturesBoard departures={departures} />}
    </div>
  )
}