/**
 * Shared mock data for E2E tests
 * Centralizes test data to ensure consistency across test files
 */

export const mockStation = {
  id: 'de:09162:1',
  name: 'Marienplatz',
  latitude: 48.137154,
  longitude: 11.576124,
  zone_id: 'M',
  wheelchair_boarding: 1,
}

export const mockSecondStation = {
  id: 'de:09162:2',
  name: 'Hauptbahnhof',
  latitude: 48.140232,
  longitude: 11.558335,
  zone_id: 'M',
  wheelchair_boarding: 1,
}

export const mockDepartures = [
  {
    trip_id: 'trip_1',
    route_id: 'U3',
    route_short_name: 'U3',
    route_long_name: 'U-Bahn Line 3',
    headsign: 'Moosach',
    stop_id: mockStation.id,
    stop_name: mockStation.name,
    scheduled_departure: '2025-01-01T10:00:00Z',
    scheduled_arrival: null,
    realtime_departure: '2025-01-01T10:02:00Z',
    realtime_arrival: null,
    departure_delay_seconds: 120,
    arrival_delay_seconds: null,
    schedule_relationship: 'SCHEDULED',
    vehicle_id: null,
    alerts: [],
  },
  {
    trip_id: 'trip_2',
    route_id: 'S1',
    route_short_name: 'S1',
    route_long_name: 'S-Bahn Line 1',
    headsign: 'Flughafen',
    stop_id: mockStation.id,
    stop_name: mockStation.name,
    scheduled_departure: '2025-01-01T10:05:00Z',
    scheduled_arrival: null,
    realtime_departure: '2025-01-01T10:05:00Z',
    realtime_arrival: null,
    departure_delay_seconds: 0,
    arrival_delay_seconds: null,
    schedule_relationship: 'SCHEDULED',
    vehicle_id: null,
    alerts: [],
  },
]

export const mockCancelledDeparture = {
  trip_id: 'trip_cancelled',
  route_id: 'U6',
  route_short_name: 'U6',
  route_long_name: 'U-Bahn Line 6',
  headsign: 'Garching',
  stop_id: mockStation.id,
  stop_name: mockStation.name,
  scheduled_departure: '2025-01-01T10:15:00Z',
  scheduled_arrival: null,
  realtime_departure: null,
  realtime_arrival: null,
  departure_delay_seconds: null,
  arrival_delay_seconds: null,
  schedule_relationship: 'CANCELED',
  vehicle_id: null,
  alerts: [],
}

export const mockStationStats = {
  station_id: mockStation.id,
  station_name: mockStation.name,
  time_range: '24h',
  total_departures: 100,
  cancelled_count: 5,
  cancellation_rate: 0.05,
  delayed_count: 10,
  delay_rate: 0.1,
  network_avg_cancellation_rate: 0.03,
  network_avg_delay_rate: 0.08,
  performance_score: 82,
  by_transport: [
    { transport_type: 'U-Bahn', total: 50, cancelled: 2, delayed: 5 },
    { transport_type: 'S-Bahn', total: 50, cancelled: 3, delayed: 5 },
  ],
  data_from: '2025-01-01T00:00:00Z',
  data_to: '2025-01-02T00:00:00Z',
}

export const mockStationTrends = {
  station_id: mockStation.id,
  station_name: mockStation.name,
  granularity: 'hour',
  time_range: '24h',
  data_points: [
    {
      timestamp: '2025-01-01T00:00:00Z',
      total_departures: 10,
      cancelled_count: 0,
      delayed_count: 1,
      cancellation_rate: 0,
      delay_rate: 0.1,
    },
    {
      timestamp: '2025-01-01T01:00:00Z',
      total_departures: 8,
      cancelled_count: 1,
      delayed_count: 0,
      cancellation_rate: 0.125,
      delay_rate: 0,
    },
  ],
}

export const mockHeatmapData = {
  time_range: '24h',
  generated_at: '2025-01-01T12:00:00Z',
  total_stations: 150,
  stations: [
    {
      stop_id: mockStation.id,
      stop_name: mockStation.name,
      latitude: mockStation.latitude,
      longitude: mockStation.longitude,
      total_departures: 100,
      cancellation_rate: 0.05,
      delay_rate: 0.1,
      performance_score: 82,
    },
    {
      stop_id: mockSecondStation.id,
      stop_name: mockSecondStation.name,
      latitude: mockSecondStation.latitude,
      longitude: mockSecondStation.longitude,
      total_departures: 200,
      cancellation_rate: 0.02,
      delay_rate: 0.05,
      performance_score: 93,
    },
  ],
}

export const mockHealthResponse = {
  status: 'ok',
  version: '1.0.0',
  uptime_seconds: 3600,
}

/**
 * Helper to apply common API mocks for a page
 */
export function setupStationMocks(page: import('@playwright/test').Page) {
  return Promise.all([
    page.route('**/api/v1/transit/stops/search**', async route => {
      const url = new URL(route.request().url())
      const query = (url.searchParams.get('query') || '').toLowerCase()

      if (query.includes('mar')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ query, results: [mockStation] }),
        })
      }
      if (query.includes('haupt')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ query, results: [mockSecondStation] }),
        })
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ query, results: [] }),
      })
    }),

    page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStationStats),
      })
    }),

    page.route('**/api/v1/transit/stops/**/trends**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStationTrends),
      })
    }),

    page.route('**/api/v1/transit/departures**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stop: mockStation,
          departures: mockDepartures,
          realtime_available: true,
        }),
      })
    }),
  ])
}

export function setupHeatmapMocks(page: import('@playwright/test').Page) {
  return page.route('**/api/v1/heatmap**', async route => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockHeatmapData),
    })
  })
}

export function setupHealthMocks(page: import('@playwright/test').Page) {
  return page.route('**/api/v1/health**', async route => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockHealthResponse),
    })
  })
}
