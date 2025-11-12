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
          station: { id: 'de:09162:1', name: 'Central Station', place: 'Munich' },
          departures: [],
        },
      },
      isLoading: false,
      error: null,
    } as unknown as UseQueryResult)
    vi.clearAllMocks()
  })

  it('renders station heading and passes data to departures board', () => {
    render(
      <MemoryRouter initialEntries={['/departures/de:09162:1']}>
        <Routes>
          <Route path="/departures/:stationId" element={<DeparturesPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Departures for Central Station')).toBeInTheDocument()
    expect(screen.getByTestId('departures-board')).toHaveTextContent('0 departures')
    expect(screen.getByText('Transport Types')).toBeInTheDocument()

    const [params, options] = mockUseDepartures.mock.calls[0]
    expect(params).toMatchObject({ station: 'de:09162:1', limit: 20, offset: 0 })
    expect(options).toMatchObject({ enabled: true, live: true })
  })
})
