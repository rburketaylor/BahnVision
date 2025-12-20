import { test, expect } from '@playwright/test'

const mockStation = {
  id: 'de:09162:1',
  name: 'Marienplatz',
  latitude: 48.137154,
  longitude: 11.576124,
  zone_id: 'M',
  wheelchair_boarding: 1,
}

const mockDepartures = [
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

const mockStationStats = {
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
  by_transport: [],
  data_from: '2025-01-01T00:00:00Z',
  data_to: '2025-01-02T00:00:00Z',
}

test.describe('Primary user journeys', () => {
  test('user can search for a station and view departures', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      const url = new URL(route.request().url())
      const query = (url.searchParams.get('query') || '').toLowerCase()

      if (query.includes('mar')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            query,
            results: [mockStation],
          }),
        })
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ query, results: [] }),
      })
    })

    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockStationStats,
        }),
      })
    })

    await page.route('**/api/v1/transit/departures**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stop: mockStation,
          departures: mockDepartures,
          realtime_available: true,
        }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Marienplatz')

    await page.getByRole('button', { name: /Marienplatz/ }).click()

    await expect(page).toHaveURL(/\/station\/de:09162:1$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Marienplatz/)

    await page.getByRole('button', { name: 'Schedule' }).click()

    await expect(page.getByRole('heading', { name: /2 departures/i })).toBeVisible()
    await expect(page.getByText('Moosach')).toBeVisible()
    await expect(page.getByText('Flughafen')).toBeVisible()
  })
})
