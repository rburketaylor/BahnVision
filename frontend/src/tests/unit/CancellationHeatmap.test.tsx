/**
 * Tests for MapLibreHeatmap component
 * Validates rendering and loading states
 *
 * Note: MapLibre GL requires WebGL context; we mock maplibre-gl for unit tests
 */

import { describe, it, expect, vi, beforeAll, afterAll, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { useTheme } from '../../contexts/ThemeContext'

// Mock maplibre-gl since it requires WebGL - use class syntax for proper constructor behavior
vi.mock('maplibre-gl', () => {
  // Mock types for maplibre features
  type SourceConfig = { type: string; data?: unknown; cluster?: boolean }
  type LayerConfig = { id: string; type: string; source?: string }
  type EventHandler = (...args: unknown[]) => void

  // Mock Map class
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const MockMap = vi.fn().mockImplementation(function (this: Record<string, any>) {
    const sources = new Map<string, SourceConfig & { setData: ReturnType<typeof vi.fn> }>()
    const layers = new Map<string, LayerConfig>()
    const handlers = new Map<string, EventHandler[]>()

    const registerHandler = (key: string, cb: EventHandler) => {
      const list = handlers.get(key) ?? []
      list.push(cb)
      handlers.set(key, list)
    }

    this._emit = (key: string, ...args: unknown[]) => {
      const list = handlers.get(key) ?? []
      list.forEach(cb => cb(...args))
    }

    this.on = vi.fn((event: string, layerOrCb: unknown, cbMaybe?: unknown) => {
      if (typeof layerOrCb === 'string' && typeof cbMaybe === 'function') {
        registerHandler(`${event}:${layerOrCb}`, cbMaybe as EventHandler)
        return this
      }

      if (typeof layerOrCb === 'function') {
        registerHandler(event, layerOrCb as EventHandler)
      }
      return this
    })
    this.remove = vi.fn()
    this.addControl = vi.fn()
    this.addSource = vi.fn((id: string, source: SourceConfig) => {
      const wrapped = {
        ...source,
        setData: vi.fn(),
        getClusterLeaves: vi.fn().mockResolvedValue([]),
      }
      sources.set(id, wrapped)
    })
    this.addLayer = vi.fn((layer: LayerConfig) => {
      layers.set(layer.id, layer)
    })
    this.getSource = vi.fn((id: string) => sources.get(id))
    this.getZoom = vi.fn(() => 6)
    this.getCenter = vi.fn(() => ({ lng: 10.4, lat: 51.1 }))
    this.isStyleLoaded = vi.fn(() => true)
    this.getCanvas = vi.fn(() => ({ style: {} }))
    this.queryRenderedFeatures = vi.fn(() => [])
    this.getLayer = vi.fn((id: string) => layers.get(id))
    this.setStyle = vi.fn()
    this.fitBounds = vi.fn()
    this.easeTo = vi.fn()
  })

  // Mock NavigationControl
  const MockNavigationControl = vi.fn()

  // Mock Popup class
  const MockPopup = vi.fn().mockImplementation(function (this: Record<string, unknown>) {
    const handlers = new Map<string, Array<() => void>>()
    this._emit = (event: string) => {
      const list = handlers.get(event) ?? []
      list.forEach(cb => cb())
    }
    this.on = vi.fn((event: string, cb: () => void) => {
      const list = handlers.get(event) ?? []
      list.push(cb)
      handlers.set(event, list)
      return this
    })
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
    private sw: { lng: number; lat: number }
    private ne: { lng: number; lat: number }

    constructor(sw: [number, number], ne: [number, number]) {
      this.sw = { lng: sw[0], lat: sw[1] }
      this.ne = { lng: ne[0], lat: ne[1] }
    }

    extend(coords: [number, number]) {
      const [lng, lat] = coords
      this.sw = { lng: Math.min(this.sw.lng, lng), lat: Math.min(this.sw.lat, lat) }
      this.ne = { lng: Math.max(this.ne.lng, lng), lat: Math.max(this.ne.lat, lat) }
      return this
    }
    getSouthWest() {
      return this.sw
    }
    getNorthEast() {
      return this.ne
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
import maplibregl from 'maplibre-gl'

function ThemeToggler() {
  const { toggleTheme } = useTheme()
  return (
    <button type="button" onClick={toggleTheme}>
      Toggle theme
    </button>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MockedMapInstance = Record<string, any>

function getMockMapInstance(): MockedMapInstance {
  const mapConstructor = (
    maplibregl as unknown as { Map: { mock: { instances: MockedMapInstance[] } } }
  ).Map
  const instance = mapConstructor.mock.instances[0]
  if (!instance) {
    throw new Error('Expected MapLibre map instance to be constructed')
  }
  return instance
}

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

  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
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

  it('initializes map and installs heatmap layers on load', async () => {
    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" />
      </ThemeProvider>
    )

    await waitFor(() => {
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    })

    const map = getMockMapInstance()
    map._emit('load')
    map._emit('style.load')

    expect(map.addSource).toHaveBeenCalledWith('heatmap-data', expect.any(Object))
    expect(map.addLayer).toHaveBeenCalled()
  })

  it('creates hotspot markers for high-intensity clusters', async () => {
    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map._emit('load')
    map._emit('style.load')

    map.queryRenderedFeatures.mockImplementation((query: { layers?: string[] }) => {
      if (query?.layers?.includes('clusters')) {
        return [
          {
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [10.4, 51.1] },
            properties: { cluster_id: 1, point_count: 50, intensity_sum: 50 },
          },
        ]
      }
      return []
    })

    vi.useFakeTimers()
    map._emit('zoomend')
    vi.advanceTimersByTime(300)

    expect((maplibregl as unknown as { Marker: { mock: unknown } }).Marker).toHaveBeenCalled()
  })

  it('opens a popup and escapes station name on point click, and clears selection on Escape', async () => {
    const onStationSelect = vi.fn()

    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" onStationSelect={onStationSelect} />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map._emit('load')
    map._emit('style.load')

    const feature = {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [11.558, 48.14] },
      properties: {
        station_id: 'de:09162:1',
        station_name: '<script>alert(1)</script>',
        cancellation_rate: 0.2,
        delay_rate: 0.1,
        total_departures: 100,
        cancelled_count: 20,
        delayed_count: 10,
        intensity: 0.95,
      },
    }

    map.queryRenderedFeatures.mockImplementation(
      (_point: unknown, query: { layers?: string[] }) => {
        if (query?.layers?.includes('unclustered-point')) return [feature]
        return []
      }
    )

    map._emit('click:unclustered-point', { point: { x: 10, y: 10 } })

    const popupInstance = (
      maplibregl as unknown as { Popup: { mock: { instances: MockedMapInstance[] } } }
    ).Popup.mock.instances[0]
    expect(popupInstance.setHTML).toHaveBeenCalledWith(expect.stringContaining('&lt;script&gt;'))
    expect(onStationSelect).toHaveBeenCalledWith('de:09162:1')

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onStationSelect).toHaveBeenCalledWith(null)
    expect(popupInstance.remove).toHaveBeenCalled()
  })

  it('resets view, clears stored view, and eases to Germany center', async () => {
    localStorage.setItem('bahnvision-heatmap-view-v1', JSON.stringify({ center: [1, 2], zoom: 9 }))
    const onStationSelect = vi.fn()

    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" onStationSelect={onStationSelect} />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map._emit('load')

    fireEvent.click(screen.getByRole('button', { name: 'Reset map view' }))
    expect(localStorage.getItem('bahnvision-heatmap-view-v1')).toBeNull()
    expect(map.easeTo).toHaveBeenCalled()
    expect(onStationSelect).toHaveBeenCalledWith(null)
  })

  it('recreates map instance when theme toggles', async () => {
    // The component recreates the map when theme changes (resolvedTheme in useEffect deps)
    // rather than calling setStyle
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeToggler />
        <MapLibreHeatmap dataPoints={[]} metric="cancellations" />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map._emit('load')
    map._emit('style.load')

    // Click to toggle theme from light to dark
    fireEvent.click(screen.getByRole('button', { name: 'Toggle theme' }))

    // Wait for the map to be recreated (useEffect cleanup and re-init)
    await waitFor(() => {
      expect(
        (maplibregl as unknown as { Map: { mock: { calls: unknown[][] } } }).Map.mock.calls.length
      ).toBe(2)
    })

    // Verify the old map was removed
    expect(map.remove).toHaveBeenCalled()
  })
})
