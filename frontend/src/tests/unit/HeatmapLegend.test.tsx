import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { HeatmapLegend } from '../../components/heatmap/HeatmapLegend'
import { getBVVMarkerColor } from '../../components/heatmap/markerStyles'

describe('HeatmapLegend', () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it('renders combined title and items when both metrics enabled', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <HeatmapLegend enabledMetrics={{ cancellations: true, delays: true }} />
      </ThemeProvider>
    )

    expect(screen.getByText('Combined Intensity')).toBeInTheDocument()
    expect(screen.getByText('Low impact')).toBeInTheDocument()
    expect(screen.getByText('0-5%')).toBeInTheDocument()
    expect(screen.getByText('Severe')).toBeInTheDocument()
    expect(screen.getByText('>25%')).toBeInTheDocument()

    const lowSwatch = screen.getByText('Low impact').closest('div.flex')?.firstElementChild
    const moderateSwatch = screen
      .getByText('Moderate impact')
      .closest('div.flex')?.firstElementChild

    expect(lowSwatch).toHaveStyle({ backgroundColor: getBVVMarkerColor(0.1) })
    expect(moderateSwatch).toHaveStyle({ backgroundColor: getBVVMarkerColor(0.4) })
  })

  it('renders delay-only title and items when only delays enabled', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <HeatmapLegend enabledMetrics={{ cancellations: false, delays: true }} />
      </ThemeProvider>
    )

    expect(screen.getByText('Delay Intensity')).toBeInTheDocument()
    expect(screen.getAllByText('Medium').length).toBeGreaterThan(0)
    expect(screen.getByText('5-10%')).toBeInTheDocument()
  })

  it('renders cancellation-only title and supports hover highlighting', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <HeatmapLegend enabledMetrics={{ cancellations: true, delays: false }} />
      </ThemeProvider>
    )

    expect(screen.getByText('Cancellation Intensity')).toBeInTheDocument()
    const firstItem = screen.getByText('0-2%').closest('div')
    expect(firstItem).toBeTruthy()

    fireEvent.mouseEnter(firstItem!)
    expect(firstItem).toHaveClass('bg-surface-elevated')

    fireEvent.mouseLeave(firstItem!)
    expect(firstItem).not.toHaveClass('bg-surface-elevated')
  })
})
