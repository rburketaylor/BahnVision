import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import type { ReactNode } from 'react'
import { ThemeProvider } from '../../../contexts/ThemeContext'
import HeatmapPage from '../../../pages/HeatmapPage'
import { useHeatmap } from '../../../hooks/useHeatmap'

vi.mock('../../../hooks/useHeatmap', () => ({
  useHeatmap: vi.fn(),
}))

vi.mock('../../../components/heatmap/MapLibreHeatmap', () => ({
  MapLibreHeatmap: ({ overlay }: { overlay?: ReactNode }) => (
    <div data-testid="mock-heatmap">{overlay}</div>
  ),
}))

vi.mock('../../../components/heatmap', async () => {
  const actual = await vi.importActual<typeof import('../../../components/heatmap')>(
    '../../../components/heatmap'
  )
  return {
    ...actual,
    HeatmapSearchOverlay: () => <div data-testid="heatmap-search" />,
  }
})

const mockUseHeatmap = vi.mocked(useHeatmap)

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <HeatmapPage />
      </MemoryRouter>
    </ThemeProvider>
  )
}

describe('HeatmapPage', () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }))

    localStorage.clear()
    mockUseHeatmap.mockReturnValue({
      data: {
        time_range: { from: '2025-01-01T00:00:00Z', to: '2025-01-02T00:00:00Z' },
        data_points: [],
        summary: null,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as ReturnType<typeof useHeatmap>)
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it('restores controls state from localStorage', async () => {
    localStorage.setItem('bahnvision-heatmap-controls-open-v1', '0')

    renderPage()
    await screen.findByTestId('mock-heatmap')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Heatmap controls')).not.toBeInTheDocument()
  })

  it('toggles controls with keyboard shortcuts', async () => {
    renderPage()
    await screen.findByTestId('mock-heatmap')

    expect(screen.getByLabelText('Heatmap controls')).toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'c' })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })

    fireEvent.keyDown(window, { key: 'c' })
    await waitFor(() => {
      expect(screen.getByLabelText('Heatmap controls')).toBeInTheDocument()
    })

    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show heatmap controls/i })).toBeInTheDocument()
    })
  })

  it('shows error state and allows refresh', async () => {
    const refetch = vi.fn()
    mockUseHeatmap.mockReturnValue({
      data: {
        time_range: { from: '2025-01-01T00:00:00Z', to: '2025-01-02T00:00:00Z' },
        data_points: [],
        summary: null,
      },
      isLoading: false,
      error: new Error('Boom'),
      refetch,
    } as ReturnType<typeof useHeatmap>)

    renderPage()
    await screen.findByTestId('mock-heatmap')

    expect(screen.getByText('Failed to load heatmap data')).toBeInTheDocument()
    expect(screen.getByText('Boom')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /refresh heatmap data/i }))
    expect(refetch).toHaveBeenCalled()
  })
})
