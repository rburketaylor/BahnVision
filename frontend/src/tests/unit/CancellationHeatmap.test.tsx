/**
 * Tests for MapLibreHeatmap component
 * Validates rendering and loading states
 *
 * Note: MapLibre GL requires WebGL context; we mock maplibre-gl for unit tests
 */

import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'

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
    this.isStyleLoaded = vi.fn(() => true)
    this.getCanvas = vi.fn(() => ({ style: {} }))
    this.queryRenderedFeatures = vi.fn(() => [])
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

  return {
    default: {
      Map: MockMap,
      NavigationControl: MockNavigationControl,
      Popup: MockPopup,
    },
  }
})

// Import after mocking
import { MapLibreHeatmap } from '../../components/heatmap/MapLibreHeatmap'

describe('MapLibreHeatmap Component', () => {
  beforeAll(() => {
    // Mock ResizeObserver for tests
    globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }))
  })

  it('should show loading state when isLoading is true', () => {
    render(<MapLibreHeatmap dataPoints={[]} isLoading={true} metric="cancellations" />)

    expect(screen.getByText('Loading heatmap data...')).toBeInTheDocument()
  })

  it('should not show loading overlay when isLoading is false', () => {
    render(<MapLibreHeatmap dataPoints={[]} isLoading={false} metric="cancellations" />)

    expect(screen.queryByText('Loading heatmap data...')).not.toBeInTheDocument()
  })

  it('should render the map container', () => {
    const { container } = render(<MapLibreHeatmap dataPoints={[]} metric="cancellations" />)

    // Check that the container div exists
    expect(container.querySelector('.relative')).toBeInTheDocument()
  })
})
