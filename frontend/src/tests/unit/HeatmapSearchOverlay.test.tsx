import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { HeatmapSearchOverlay } from '../../components/heatmap/HeatmapSearchOverlay'
import type { TransitStop } from '../../types/gtfs'

vi.mock('../../components/features/station/StationSearch', () => ({
  StationSearch: ({
    onSelect,
    autoFocus,
  }: {
    onSelect: (stop: TransitStop) => void
    autoFocus?: boolean
  }) => (
    <div>
      <input aria-label="Station search input" autoFocus={autoFocus} />
      <button
        type="button"
        onClick={() =>
          onSelect({
            id: 'stop-1',
            name: 'Test Station',
            latitude: 1,
            longitude: 2,
            zone_id: null,
            wheelchair_boarding: 0,
          })
        }
      >
        Select Station
      </button>
    </div>
  ),
}))

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderOverlay(ui: React.ReactNode, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/"
          element={
            <>
              <LocationDisplay />
              {ui}
            </>
          }
        />
        <Route path="/station/:stationId" element={<LocationDisplay />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('HeatmapSearchOverlay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts collapsed and expands via click', async () => {
    const user = userEvent.setup()
    renderOverlay(<HeatmapSearchOverlay />)

    expect(screen.getByRole('button', { name: 'Search stations (S)' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search stations (S)' }))
    expect(screen.getByText('Find Station')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close search (Escape)' })).toBeInTheDocument()
  })

  it('toggles via keyboard and closes with Escape', async () => {
    const user = userEvent.setup()
    renderOverlay(<HeatmapSearchOverlay />)

    await user.keyboard('s')
    expect(screen.getByText('Find Station')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Search stations (S)' })).toBeInTheDocument()
  })

  it('selects a station, calls callback, and navigates to details', async () => {
    const user = userEvent.setup()
    const onStationSelect = vi.fn()
    renderOverlay(<HeatmapSearchOverlay onStationSelect={onStationSelect} />)

    await user.click(screen.getByRole('button', { name: 'Search stations (S)' }))
    await user.click(screen.getByRole('button', { name: 'Select Station' }))

    expect(onStationSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'stop-1' }))
    expect(screen.getByText('Test Station')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View Details' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'View Details' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/station/stop-1')
  })

  it('does not toggle with S when typing in the input', async () => {
    const user = userEvent.setup()
    renderOverlay(<HeatmapSearchOverlay />)

    await user.keyboard('s')
    const input = screen.getByLabelText('Station search input')
    await user.click(input)

    await user.keyboard('s')
    expect(screen.getByText('Find Station')).toBeInTheDocument()
  })

  it('hides details link when configured', async () => {
    const user = userEvent.setup()
    renderOverlay(<HeatmapSearchOverlay showDetailsLink={false} />)

    await user.click(screen.getByRole('button', { name: 'Search stations (S)' }))
    await user.click(screen.getByRole('button', { name: 'Select Station' }))

    expect(screen.queryByRole('button', { name: 'View Details' })).not.toBeInTheDocument()
  })
})
