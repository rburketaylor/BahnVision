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

vi.mock('react-dom/client', () => {
  return {
    createRoot: vi.fn(() => ({
      render: vi.fn(),
      unmount: vi.fn(),
    })),
  }
})

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
    this.setDOMContent = vi.fn().mockReturnThis()
    this.addTo = vi.fn().mockReturnThis()
    this.remove = vi.fn()
    this.isOpen = vi.fn(() => false)
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
import { createRoot } from 'react-dom/client'
import type { HeatmapDataPoint, HeatmapEnabledMetrics } from '../../types/heatmap'

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
  const instance = mapConstructor.mock.instances.at(-1)
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
        <MapLibreHeatmap
          dataPoints={[]}
          isLoading={true}
          enabledMetrics={{ cancellations: true, delays: true }}
        />
      </ThemeProvider>
    )

    expect(screen.getByText('Loading heatmap data...')).toBeInTheDocument()
  })

  it('should not show loading overlay when isLoading is false', () => {
    render(
      <ThemeProvider>
        <MapLibreHeatmap
          dataPoints={[]}
          isLoading={false}
          enabledMetrics={{ cancellations: true, delays: true }}
        />
      </ThemeProvider>
    )

    expect(screen.queryByText('Loading heatmap data...')).not.toBeInTheDocument()
  })

  it('should render the map container', () => {
    const { container } = render(
      <ThemeProvider>
        <MapLibreHeatmap dataPoints={[]} enabledMetrics={{ cancellations: true, delays: true }} />
      </ThemeProvider>
    )

    // Check that the container div exists
    expect(container.querySelector('.relative')).toBeInTheDocument()
  })

  it('initializes map and installs heatmap layers on load', async () => {
    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap dataPoints={[]} enabledMetrics={{ cancellations: true, delays: true }} />
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

  it('applies focus request after load with default zoom floor', async () => {
    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap
          dataPoints={[]}
          enabledMetrics={{ cancellations: true, delays: true }}
          focusRequest={{
            requestId: 1,
            stopId: 'stop-1',
            lat: 52.5,
            lon: 13.4,
            source: 'search',
          }}
        />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map.getZoom.mockReturnValue(6)
    map._emit('load')

    expect(map.easeTo).toHaveBeenCalledWith(
      expect.objectContaining({
        center: [13.4, 52.5],
        zoom: 12,
        duration: 650,
      })
    )
  })

  it('does not zoom out when already zoomed in for focus request', async () => {
    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap
          dataPoints={[]}
          enabledMetrics={{ cancellations: true, delays: true }}
          focusRequest={{
            requestId: 2,
            stopId: 'stop-2',
            lat: 48.1,
            lon: 11.6,
            source: 'search',
          }}
        />
      </ThemeProvider>
    )

    await waitFor(() =>
      expect((maplibregl as unknown as { Map: { mock: unknown } }).Map).toHaveBeenCalledTimes(1)
    )
    const map = getMockMapInstance()
    map.getZoom.mockReturnValue(14)
    map._emit('load')

    expect(map.easeTo).toHaveBeenCalledWith(
      expect.objectContaining({
        center: [11.6, 48.1],
        zoom: 14,
        duration: 650,
      })
    )
  })

  // NOTE: The "creates hotspot markers for high-intensity clusters" test was removed
  // because the pulsing hotspot marker feature was removed from the MapLibreHeatmap component

  it('calls onStationSelect when clicking a point and clears on Escape', async () => {
    const onStationSelect = vi.fn()

    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap
          dataPoints={[
            {
              station_id: 'de:09162:1',
              station_name: 'Test Station',
              latitude: 48.14,
              longitude: 11.558,
              cancellation_rate: 0.2,
              delay_rate: 0.1,
              total_departures: 100,
              cancelled_count: 20,
              delayed_count: 10,
            },
          ]}
          overviewPoints={[
            { id: 'de:09162:1', n: 'Test Station', lat: 48.14, lon: 11.558, i: 0.95 },
          ]}
          enabledMetrics={{ cancellations: true, delays: true }}
          onStationSelect={onStationSelect}
        />
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
        station_name: 'Test Station',
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

    // The click should call onStationSelect with the station ID
    expect(onStationSelect).toHaveBeenCalledWith('de:09162:1')

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onStationSelect).toHaveBeenCalledWith(null)
  })

  it('resets view, clears stored view, and eases to Germany center', async () => {
    localStorage.setItem('bahnvision-heatmap-view-v1', JSON.stringify({ center: [1, 2], zoom: 9 }))
    const onStationSelect = vi.fn()

    render(
      <ThemeProvider defaultTheme="light">
        <MapLibreHeatmap
          dataPoints={[]}
          enabledMetrics={{ cancellations: true, delays: true }}
          onStationSelect={onStationSelect}
        />
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
        <MapLibreHeatmap dataPoints={[]} enabledMetrics={{ cancellations: true, delays: true }} />
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

  it('unmounts the popup root when the component unmounts', async () => {
    const { unmount } = render(
      <ThemeProvider>
        <MapLibreHeatmap
          overviewPoints={[
            {
              id: 'station-1',
              n: 'Station',
              lat: 52.5,
              lon: 13.4,
              i: 0.2,
            },
          ]}
          selectedStationId="station-1"
          enabledMetrics={{ cancellations: true, delays: true }}
        />
      </ThemeProvider>
    )

    await waitFor(() => expect(createRoot).toHaveBeenCalled())
    const rootInstance = (createRoot as unknown as { mock: { results: Array<{ value: unknown }> } })
      .mock.results[0]?.value as { unmount: ReturnType<typeof vi.fn> } | undefined
    expect(rootInstance?.unmount).toBeDefined()

    unmount()
    expect(rootInstance!.unmount).toHaveBeenCalled()
  })

  it('does not let a stale popup close unmount a newly selected station popup', async () => {
    const overviewPoints = [
      { id: 'station-1', n: 'Station 1', lat: 52.5, lon: 13.4, i: 0.2 },
      { id: 'station-2', n: 'Station 2', lat: 52.6, lon: 13.5, i: 0.2 },
    ]

    const { rerender } = render(
      <ThemeProvider>
        <MapLibreHeatmap
          overviewPoints={overviewPoints}
          selectedStationId="station-1"
          enabledMetrics={{ cancellations: true, delays: true }}
        />
      </ThemeProvider>
    )

    await waitFor(() => expect(createRoot).toHaveBeenCalledTimes(1))
    const firstRoot = (createRoot as unknown as { mock: { results: Array<{ value: unknown }> } })
      .mock.results[0]?.value as { unmount: ReturnType<typeof vi.fn> } | undefined
    expect(firstRoot?.unmount).toBeDefined()

    // Simulate MapLibre emitting a popup close (e.g., clicking another point).
    const popupInstance = (
      maplibregl as unknown as { Popup: { mock: { instances: Array<Record<string, unknown>> } } }
    ).Popup.mock.instances.at(-1) as { _emit?: (event: string) => void } | undefined
    expect(popupInstance?._emit).toBeTypeOf('function')
    popupInstance!._emit!('close')

    // Immediately switch to another station before the close handler's async cleanup runs.
    rerender(
      <ThemeProvider>
        <MapLibreHeatmap
          overviewPoints={overviewPoints}
          selectedStationId="station-2"
          enabledMetrics={{ cancellations: true, delays: true }}
        />
      </ThemeProvider>
    )

    // The second selection should render into a new root, not be unmounted by the prior close.
    await waitFor(() => expect(createRoot).toHaveBeenCalledTimes(2))
    const secondRoot = (createRoot as unknown as { mock: { results: Array<{ value: unknown }> } })
      .mock.results[1]?.value as { unmount: ReturnType<typeof vi.fn> } | undefined
    expect(secondRoot?.unmount).toBeDefined()
    await waitFor(() => expect(firstRoot!.unmount).toHaveBeenCalledTimes(1))
    expect(secondRoot!.unmount).not.toHaveBeenCalled()
  })

  it('resets map instance on error boundary retry', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const dataPoints: HeatmapDataPoint[] = []
    const enabledMetrics: HeatmapEnabledMetrics = { cancellations: true, delays: true }
    const StableOverlay = () => null
    const ThrowingOverlay = () => {
      throw new Error('boom')
    }

    const { rerender } = render(
      <ThemeProvider>
        <MapLibreHeatmap
          dataPoints={dataPoints}
          isLoading={false}
          enabledMetrics={enabledMetrics}
          overlay={<StableOverlay />}
        />
      </ThemeProvider>
    )

    await waitFor(() => {
      expect((maplibregl as unknown as { Map: ReturnType<typeof vi.fn> }).Map).toHaveBeenCalled()
    })

    rerender(
      <ThemeProvider>
        <MapLibreHeatmap
          dataPoints={dataPoints}
          isLoading={false}
          enabledMetrics={enabledMetrics}
          overlay={<ThrowingOverlay />}
        />
      </ThemeProvider>
    )

    expect(await screen.findByText('Heatmap Error')).toBeInTheDocument()
    const currentMapInstance = getMockMapInstance()
    currentMapInstance.remove.mockClear()
    fireEvent.click(screen.getByText('Retry'))

    expect(currentMapInstance.remove).toHaveBeenCalled()
    consoleError.mockRestore()
  })
})
