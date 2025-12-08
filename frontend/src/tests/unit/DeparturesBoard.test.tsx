import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { DeparturesBoard } from '../../components/DeparturesBoard'
import type { TransitDeparture } from '../../types/gtfs'

const baseDeparture: TransitDeparture = {
  trip_id: 'trip_1',
  route_id: 'U1',
  route_short_name: 'U1',
  route_long_name: 'U-Bahn Line 1',
  headsign: 'Default Destination',
  stop_id: 'de:09162:6',
  stop_name: 'Marienplatz',
  scheduled_departure: '2024-01-01T10:00:00Z',
  scheduled_arrival: null,
  realtime_departure: '2024-01-01T10:00:00Z',
  realtime_arrival: null,
  departure_delay_seconds: 0,
  arrival_delay_seconds: null,
  schedule_relationship: 'SCHEDULED',
  vehicle_id: null,
  alerts: [],
}

const buildDeparture = (overrides: Partial<TransitDeparture>): TransitDeparture => ({
  ...baseDeparture,
  ...overrides,
})

describe('DeparturesBoard', () => {
  it('orders departures by effective realtime/scheduled timestamps', () => {
    const departures: TransitDeparture[] = [
      buildDeparture({
        headsign: 'Later Train',
        route_short_name: 'U6',
        scheduled_departure: '2024-01-01T10:00:00Z',
        realtime_departure: '2024-01-01T10:10:00Z',
      }),
      buildDeparture({
        headsign: 'Early Planned',
        route_short_name: 'BUS',
        scheduled_departure: '2024-01-01T09:50:00Z',
        realtime_departure: null,
      }),
      buildDeparture({
        headsign: 'Earlier Real',
        route_short_name: 'TRAM',
        scheduled_departure: '2024-01-01T10:05:00Z',
        realtime_departure: '2024-01-01T10:00:00Z',
      }),
    ]

    render(<DeparturesBoard departures={departures} />)

    const destinationsInOrder = screen
      .getAllByText(/Later Train|Early Planned|Earlier Real/)
      .map(element => element.textContent)

    expect(destinationsInOrder).toEqual(['Early Planned', 'Earlier Real', 'Later Train'])
  })

  it('toggles between 24h and 12h display', async () => {
    const user = userEvent.setup()
    const departures: TransitDeparture[] = [
      buildDeparture({
        headsign: 'Afternoon Train',
        scheduled_departure: '2024-01-01T13:00:00Z',
        realtime_departure: '2024-01-01T13:00:00Z',
      }),
    ]

    render(<DeparturesBoard departures={departures} use24Hour={true} />)

    const toggleButton = screen.getByText('24').closest('button')
    expect(toggleButton).toBeInTheDocument()

    await user.click(toggleButton!)
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('highlights cancelled departures with the warning background', () => {
    const departures: TransitDeparture[] = [
      buildDeparture({
        headsign: 'Normal Service',
      }),
      buildDeparture({
        headsign: 'Cancelled Service',
        schedule_relationship: 'SKIPPED',
      }),
    ]

    render(<DeparturesBoard departures={departures} />)

    const cancelledCard = screen.getByText('Cancelled Service').closest('[class*="bg-"]')
    expect(cancelledCard?.className).toContain('bg-red-')
  })

  it('shows empty-state message when no departures are available', () => {
    render(<DeparturesBoard departures={[]} />)
    expect(screen.getByText('No departures found')).toBeInTheDocument()
    expect(screen.getByText('Try adjusting your filters or time range')).toBeInTheDocument()
  })
})
