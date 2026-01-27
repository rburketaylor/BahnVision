import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { HeatmapLegend } from '../../components/heatmap/HeatmapLegend'

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
    const { container } = render(
      <ThemeProvider defaultTheme="light">
        <HeatmapLegend enabledMetrics={{ cancellations: true, delays: false }} />
      </ThemeProvider>
    )

    expect(screen.getByText('Cancellation Intensity')).toBeInTheDocument()
    const firstItem = screen.getByText('0-2%').closest('div')
    expect(firstItem).toBeTruthy()

    fireEvent.mouseEnter(firstItem!)
    expect(container.querySelector('.bg-muted\\/50')).toBeInTheDocument()

    fireEvent.mouseLeave(firstItem!)
    expect(container.querySelector('.bg-muted\\/50')).not.toBeInTheDocument()
  })
})
