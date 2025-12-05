import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
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
            wheelchair_boarding: 1
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
    render(
      <MemoryRouter initialEntries={['/departures/de:09162:1']}>
        <Routes>
          <Route path="/departures/:stationId" element={<DeparturesPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Departures for Central Station')).toBeInTheDocument()
    expect(screen.getByTestId('departures-board')).toHaveTextContent('0 departures')

    const [params, options] = mockUseDepartures.mock.calls[0]
    expect(params).toMatchObject({ stop_id: 'de:09162:1', limit: 20, offset_minutes: 0 })
    expect(options).toMatchObject({ enabled: true, live: true })
  })
})
