import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { StationPopup } from '../../components/heatmap/StationPopup'
import type { HeatmapPointLight } from '../../types/heatmap'
import type { StationStats } from '../../types/gtfs'

describe('StationPopup', () => {
  const station: HeatmapPointLight = {
    id: 'station-1',
    n: 'Station Name',
    lat: 52.5,
    lon: 13.4,
    i: 0.2,
  }

  it('renders loading state', () => {
    render(<StationPopup station={station} isLoading={true} />)
    expect(screen.getByText('Loading details...')).toBeInTheDocument()
  })

  it('renders no-data message when details are missing', () => {
    const { container } = render(<StationPopup station={station} isLoading={false} />)
    expect(screen.getByText('No real-time data available for this station.')).toBeInTheDocument()
    expect(container.querySelector('.bg-status-critical')).toBeInTheDocument()
  })

  it('renders station details and by-transport breakdown', () => {
    const details: StationStats = {
      station_id: 'station-1',
      station_name: 'Station Name (Realtime)',
      time_range: '24h',
      total_departures: 1234,
      cancelled_count: 12,
      cancellation_rate: 0.02,
      delayed_count: 34,
      delay_rate: 0.03,
      network_avg_cancellation_rate: null,
      network_avg_delay_rate: null,
      performance_score: null,
      by_transport: [
        {
          transport_type: 'UBAHN',
          display_name: 'U-Bahn',
          total_departures: 100,
          cancelled_count: 1,
          cancellation_rate: 0.01,
          delayed_count: 2,
          delay_rate: 0.02,
        },
      ],
      data_from: '2026-01-01T00:00:00Z',
      data_to: '2026-01-02T00:00:00Z',
    }

    const { container } = render(
      <StationPopup station={station} details={details} isLoading={false} />
    )

    expect(screen.getByText('Station Name (Realtime)')).toBeInTheDocument()
    expect(screen.getByText('Departures')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
    expect(screen.getByText('Cancellations')).toBeInTheDocument()
    expect(screen.getByText((_, node) => node?.textContent === '12 (2.0%)')).toBeInTheDocument()
    expect(screen.getByText('By Transport Type')).toBeInTheDocument()
    expect(screen.getByText('U-Bahn')).toBeInTheDocument()
    expect(screen.getByText('3.0%')).toBeInTheDocument()
    expect(container.querySelector('.bg-status-healthy')).toBeInTheDocument()
  })

  it('uses critical accent when combined realtime rate is high', () => {
    const details: StationStats = {
      station_id: 'station-1',
      station_name: 'Station Name',
      time_range: '24h',
      total_departures: 10,
      cancelled_count: 2,
      cancellation_rate: 0.12,
      delayed_count: 1,
      delay_rate: 0.06,
      network_avg_cancellation_rate: null,
      network_avg_delay_rate: null,
      performance_score: null,
      by_transport: [],
      data_from: '2026-01-01T00:00:00Z',
      data_to: '2026-01-02T00:00:00Z',
    }

    const { container } = render(
      <StationPopup station={station} details={details} isLoading={false} />
    )
    expect(container.querySelector('.bg-status-critical')).toBeInTheDocument()
  })

  it('uses warning accent when combined realtime rate is moderate', () => {
    const details: StationStats = {
      station_id: 'station-1',
      station_name: 'Station Name',
      time_range: '24h',
      total_departures: 10,
      cancelled_count: 1,
      cancellation_rate: 0.03,
      delayed_count: 1,
      delay_rate: 0.04,
      network_avg_cancellation_rate: null,
      network_avg_delay_rate: null,
      performance_score: null,
      by_transport: [],
      data_from: '2026-01-01T00:00:00Z',
      data_to: '2026-01-02T00:00:00Z',
    }

    const { container } = render(
      <StationPopup station={station} details={details} isLoading={false} />
    )
    expect(container.querySelector('.bg-status-warning')).toBeInTheDocument()
  })
})
