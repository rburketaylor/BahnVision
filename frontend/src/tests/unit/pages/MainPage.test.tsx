import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MainPage } from '../../../pages/MainPage'
import type { TransitStop } from '../../../types/gtfs'

const mockStop: TransitStop = {
  id: 'de:09162:1',
  name: 'Marienplatz',
  latitude: 48.137154,
  longitude: 11.576124,
  zone_id: 'M',
  wheelchair_boarding: 1,
}

vi.mock('../../../components/StationSearch', () => ({
  StationSearch: ({ onSelect }: { onSelect: (stop: TransitStop) => void }) => (
    <button type="button" onClick={() => onSelect(mockStop)}>
      Select Station
    </button>
  ),
}))

describe('MainPage', () => {
  it('navigates to station details when a stop is selected', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/search']}>
          <Routes>
            <Route path="/search" element={<MainPage />} />
            <Route path="/station/:stationId" element={<div data-testid="station-view" />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    await user.click(screen.getByText('Select Station'))
    expect(screen.getByTestId('station-view')).toBeInTheDocument()
  })
})
