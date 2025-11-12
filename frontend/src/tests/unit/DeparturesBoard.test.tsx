import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
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

const getRowIndex = (label: string) => {
  const row = screen.getByText(label).closest('tr')
  const tbody = row?.parentElement
  return row && tbody ? Array.from(tbody.children).indexOf(row) : -1
}

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

    expect(getRowIndex('Early Planned')).toBeLessThan(getRowIndex('Earlier Real'))
    expect(getRowIndex('Earlier Real')).toBeLessThan(getRowIndex('Later Train'))
  })

  it('renders hour-group headers derived from the first departure in each slot', () => {
    const spy = vi.spyOn(Date.prototype, 'toLocaleString').mockImplementation(function (this: Date) {
      return `Group-${this.getHours().toString().padStart(2, '0')}`
    })

    const departures: Departure[] = [
      buildDeparture({
        destination: 'Morning Tram',
        planned_time: '2024-01-01T09:05:00Z',
        realtime_time: '2024-01-01T09:10:00Z',
      }),
      buildDeparture({
        destination: 'Late Morning Bus',
        planned_time: '2024-01-01T11:15:00Z',
        realtime_time: '2024-01-01T11:05:00Z',
      }),
    ]

    render(<DeparturesBoard departures={departures} />)

    const headers = screen.getAllByText(/^Group-/)
    const expectedOrder = departures
      .reduce<string[]>((acc, departure) => {
        const date = new Date(departure.realtime_time || departure.planned_time || '')
        const key = `Group-${date.getHours().toString().padStart(2, '0')}`
        if (!acc.includes(key)) {
          acc.push(key)
        }
        return acc
      }, [])

    expect(headers.map(cell => cell.textContent)).toEqual(expectedOrder)

    spy.mockRestore()
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

    const cancelledRow = screen.getByText('Cancelled Service').closest('tr')
    expect(cancelledRow?.className).toContain('bg-red-900/50')
  })

  it('shows empty-state message when no departures are available', () => {
    render(<DeparturesBoard departures={[]} />)
    expect(
      screen.getByText('No departures found for the selected time and filters.')
    ).toBeInTheDocument()
  })
})
