/**
 * Tests for MapLibreHeatmap component
 * Validates rendering and loading states
 *
 * Note: MapLibre GL requires WebGL context; we mock maplibre-gl for unit tests
 */

import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ThemeProvider } from '../../contexts/ThemeContext'

// Mock maplibre-gl since it requires WebGL - use class syntax for proper constructor behavior
vi.mock('maplibre-gl', () => {
  // Mock Map class
  const MockMap = vi.fn().mockImplementation(function (this: Record<string, unknown>) {
    this.on = vi.fn()
    this.remove = vi.fn()
    this.addControl = vi.fn()
    this.addSource = vi.fn()
    this.addLayer = vi.fn()
    this.getSource = vi.fn()
    this.getZoom = vi.fn(() => 6)
    this.getCenter = vi.fn(() => ({ lng: 10.4, lat: 51.1 }))
    this.isStyleLoaded = vi.fn(() => true)
    this.getCanvas = vi.fn(() => ({ style: {} }))
    this.queryRenderedFeatures = vi.fn(() => [])
    this.getLayer = vi.fn(() => undefined)
    this.setStyle = vi.fn()
    this.fitBounds = vi.fn()
    this.easeTo = vi.fn()
  })

  // Mock NavigationControl
  const MockNavigationControl = vi.fn()

  // Mock Popup class
  const MockPopup = vi.fn().mockImplementation(function (this: Record<string, unknown>) {
    this.setLngLat = vi.fn().mockReturnThis()
    this.setHTML = vi.fn().mockReturnThis()
    this.addTo = vi.fn().mockReturnThis()
    this.remove = vi.fn()
  })

  // Minimal Marker mock for hotspot overlay
  const MockMarker = vi.fn().mockImplementation(function (this: Record<string, unknown>) {
    this.setLngLat = vi.fn().mockReturnThis()
    this.addTo = vi.fn().mockReturnThis()
    this.remove = vi.fn()
  })

  // Minimal bounds mock
  class MockLngLatBounds {
    constructor() {}
    extend() {
      return this
    }
    getSouthWest() {
      return { lng: 0, lat: 0 }
    }
    getNorthEast() {
      return { lng: 0, lat: 0 }
    }
  }

  return {
    default: {
      Map: MockMap,
      NavigationControl: MockNavigationControl,
      Popup: MockPopup,
      Marker: MockMarker,
      LngLatBounds: MockLngLatBounds,
    },
  }
})

// Import after mocking
import { MapLibreHeatmap } from '../../components/heatmap/MapLibreHeatmap'

describe('MapLibreHeatmap Component', () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    // Mock ResizeObserver for tests
    globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }))

    // ThemeProvider relies on matchMedia for system theme detection
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

  it('should show loading state when isLoading is true', () => {
    render(
      <ThemeProvider>
        <MapLibreHeatmap dataPoints={[]} isLoading={true} metric="cancellations" />
      </ThemeProvider>
    )

    expect(screen.getByText('Loading heatmap data...')).toBeInTheDocument()
  })

  it('should not show loading overlay when isLoading is false', () => {
    render(
      <ThemeProvider>
        <MapLibreHeatmap dataPoints={[]} isLoading={false} metric="cancellations" />
      </ThemeProvider>
    )

    expect(screen.queryByText('Loading heatmap data...')).not.toBeInTheDocument()
  })

  it('should render the map container', () => {
    const { container } = render(
      <ThemeProvider>
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" />
      </ThemeProvider>
    )

    // Check that the container div exists
    expect(container.querySelector('.relative')).toBeInTheDocument()
  })
})
