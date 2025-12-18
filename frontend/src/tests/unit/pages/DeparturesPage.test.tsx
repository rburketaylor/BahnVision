import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import type { UseQueryResult } from '@tanstack/react-query'
import { useDepartures } from '../../../hooks/useDepartures'
import { DeparturesPage } from '../../../pages/DeparturesPage'

vi.mock('../../../hooks/useDepartures', () => ({
  useDepartures: vi.fn(),
}))

vi.mock('../../../components/DeparturesBoard', () => ({
  DeparturesBoard: ({ departures }: { departures: unknown[] }) => (
    <div data-testid="departures-board">{departures.length} departures</div>
  ),
}))

const mockUseDepartures = vi.mocked(useDepartures)

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderDeparturesPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/departures/:stationId"
          element={
            <>
              <LocationDisplay />
              <DeparturesPage />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('DeparturesPage', () => {
  beforeEach(() => {
    mockUseDepartures.mockReturnValue({
      data: {
        data: {
          stop: {
            id: 'de:09162:1',
            name: 'Central Station',
            latitude: 48.14,
            longitude: 11.558,
            zone_id: 'M',
            wheelchair_boarding: 1,
          },
          departures: [],
          realtime_available: true,
        },
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)
    vi.clearAllMocks()
  })

  it('renders stop heading and passes data to departures board', () => {
    renderDeparturesPage('/departures/de:09162:1')

    expect(screen.getByText('Departures for Central Station')).toBeInTheDocument()
    expect(screen.getByTestId('departures-board')).toHaveTextContent('0 departures')

    const [params, options] = mockUseDepartures.mock.calls[0]
    expect(params).toMatchObject({ stop_id: 'de:09162:1', limit: 20, offset_minutes: 0 })
    expect(options).toMatchObject({ enabled: true, live: true })
  })

  it('paginates forward/back and updates URL + query params', async () => {
    const user = userEvent.setup()
    renderDeparturesPage('/departures/de:09162:1')

    await user.click(screen.getByRole('button', { name: 'Next →' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/departures/de:09162:1?page=1')
    })

    const lastCallAfterNext = mockUseDepartures.mock.calls.at(-1)
    expect(lastCallAfterNext?.[0]).toMatchObject({
      stop_id: 'de:09162:1',
      limit: 20,
      offset_minutes: 30,
    })
    expect(lastCallAfterNext?.[1]).toMatchObject({ enabled: true, live: false })

    await user.click(screen.getByRole('button', { name: '← Prev' }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/departures/de:09162:1?page=0')
    })

    const lastCallAfterPrev = mockUseDepartures.mock.calls.at(-1)
    expect(lastCallAfterPrev?.[0]).toMatchObject({
      stop_id: 'de:09162:1',
      limit: 20,
      offset_minutes: 0,
    })
    expect(lastCallAfterPrev?.[1]).toMatchObject({ enabled: true, live: true })
  })

  it('switches to manual time mode and omits offset_minutes', async () => {
    renderDeparturesPage('/departures/de:09162:1')

    const timeInput = document.querySelector(
      'input[type="datetime-local"]'
    ) as HTMLInputElement | null
    expect(timeInput).not.toBeNull()
    fireEvent.change(timeInput!, { target: { value: '2025-01-01T12:34' } })

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('from=')
    })

    const lastCall = mockUseDepartures.mock.calls.at(-1)
    expect(lastCall?.[0]).toMatchObject({ stop_id: 'de:09162:1', limit: 20 })
    expect(lastCall?.[0]).not.toHaveProperty('offset_minutes')
    expect(lastCall?.[1]).toMatchObject({ enabled: true, live: false })

    fireEvent.change(timeInput!, { target: { value: '' } })

    await waitFor(() => {
      expect(screen.getByTestId('location')).not.toHaveTextContent('from=')
    })
  })
})
