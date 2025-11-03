import { useNavigate } from 'react-router'
import { StationSearch } from '../components/StationSearch'
import type { Station } from '../types/api'

export function MainPage() {
  const navigate = useNavigate()

  const handleStationSelect = (station: Station) => {
    navigate(`/departures/${station.id}`)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-center mb-8">BahnVision</h1>
      <div className="max-w-md mx-auto">
        <StationSearch onSelect={handleStationSelect} />
      </div>
    </div>
  )
}
