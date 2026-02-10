import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { StationPopup } from '../../components/heatmap/StationPopup'
import type { HeatmapPointLight } from '../../types/heatmap'
import type { StationStats } from '../../types/gtfs'

const baseStation: HeatmapPointLight = {
  id: 'de:09162:999',
  n: 'Marienplatz',
  lat: 48.1374,
  lon: 11.5755,
  i: 0.12,
}

const baseDetails: StationStats = {
  station_id: 'de:09162:999',
  station_name: 'Marienplatz (Realtime)',
  time_range: '24h',
  total_departures: 1250,
  cancelled_count: 156,
  cancellation_rate: 0.1248,
  delayed_count: 79,
  delay_rate: 0.0632,
  network_avg_cancellation_rate: null,
  network_avg_delay_rate: null,
  performance_score: null,
  by_transport: [
    {
      transport_type: 'UBAHN',
      display_name: 'U-Bahn',
      total_departures: 900,
      cancelled_count: 100,
      cancellation_rate: 0.1,
      delayed_count: 60,
      delay_rate: 0.06,
    },
  ],
  data_from: '2026-01-01T00:00:00Z',
  data_to: '2026-01-02T00:00:00Z',
}

describe('popupLayout', () => {
  it('renders semantic station details and link target from live data', () => {
    const { container } = render(
      <StationPopup station={baseStation} details={baseDetails} isLoading={false} />
    )

    expect(screen.getByRole('heading', { name: 'Marienplatz (Realtime)' })).toBeInTheDocument()
    expect(screen.getByText('Departures')).toBeInTheDocument()
    expect(screen.getByText('1,250')).toBeInTheDocument()
    expect(screen.getByText('Cancellations')).toBeInTheDocument()
    expect(screen.getByText('156 (12.5%)')).toBeInTheDocument()
    expect(screen.getByText('Delays (>5 min)')).toBeInTheDocument()
    expect(screen.getByText('79 (6.3%)')).toBeInTheDocument()
    expect(screen.getByText('By Transport Type')).toBeInTheDocument()
    expect(screen.getByText('U-Bahn')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Full Details →' })).toHaveAttribute(
      'href',
      '/station/de:09162:999'
    )
    expect(container.querySelectorAll('.bv-map-popup__row')).toHaveLength(4)
  })

  it('shows no-data fallback content when details are unavailable', () => {
    const { container } = render(<StationPopup station={baseStation} isLoading={false} />)

    expect(screen.getByText('No real-time data available for this station.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Full Details →' })).toHaveAttribute(
      'href',
      '/station/de:09162:999'
    )
    expect(container.querySelectorAll('.bv-map-popup__row')).toHaveLength(0)
  })

  it('shows loading state and keeps station navigation available', () => {
    render(<StationPopup station={baseStation} isLoading={true} />)

    expect(screen.getByText('Loading details...')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Full Details →' })).toHaveAttribute(
      'href',
      '/station/de:09162:999'
    )
  })
})
