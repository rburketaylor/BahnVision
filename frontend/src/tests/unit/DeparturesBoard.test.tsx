import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { DeparturesBoard } from '../../components/DeparturesBoard'
import type { Departure } from '../../types/api'

const baseDeparture: Departure = {
  planned_time: '2024-01-01T10:00:00Z',
  realtime_time: '2024-01-01T10:00:00Z',
  delay_minutes: 0,
  platform: '1',
  realtime: true,
  line: 'U1',
  destination: 'Default Destination',
  transport_type: 'UBAHN',
  icon: null,
  cancelled: false,
  messages: [],
}

const buildDeparture = (overrides: Partial<Departure>): Departure => ({
  ...baseDeparture,
  ...overrides,
})

describe('DeparturesBoard', () => {
  it('orders departures by effective realtime/planned timestamps', () => {
    const departures: Departure[] = [
      buildDeparture({
        destination: 'Later Train',
        line: 'U6',
        planned_time: '2024-01-01T10:00:00Z',
        realtime_time: '2024-01-01T10:10:00Z',
      }),
      buildDeparture({
        destination: 'Early Planned',
        line: 'BUS 50',
        planned_time: '2024-01-01T09:50:00Z',
        realtime_time: null,
      }),
      buildDeparture({
        destination: 'Earlier Real',
        line: 'TRAM 17',
        planned_time: '2024-01-01T10:05:00Z',
        realtime_time: '2024-01-01T10:00:00Z',
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
    const departures: Departure[] = [
      buildDeparture({
        destination: 'Afternoon Train',
        planned_time: '2024-01-01T13:00:00Z',
        realtime_time: '2024-01-01T13:00:00Z',
      }),
    ]

    render(<DeparturesBoard departures={departures} use24Hour={true} />)

    const toggleButton = screen.getByText('24').closest('button')
    expect(toggleButton).toBeInTheDocument()

    await user.click(toggleButton!)
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('highlights cancelled departures with the warning background', () => {
    const departures: Departure[] = [
      buildDeparture({
        destination: 'Normal Service',
      }),
      buildDeparture({
        destination: 'Cancelled Service',
        cancelled: true,
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
