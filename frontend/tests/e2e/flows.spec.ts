import { test, expect } from '@playwright/test'

const mockStation = {
  id: 'de:09162:1',
  name: 'Marienplatz',
  place: 'Munich',
  latitude: 48.137154,
  longitude: 11.576124,
}

const mockDeparture = {
  planned_time: '2025-01-01T10:00:00Z',
  realtime_time: '2025-01-01T10:02:00Z',
  delay_minutes: 2,
  platform: '1',
  realtime: true,
  line: 'U3',
  destination: 'Moosach',
  transport_type: 'UBAHN',
  icon: null,
  cancelled: false,
  messages: ['Minor delay'],
}

test.describe('Primary user journeys', () => {
  test('user can search for a station and view departures', async ({ page }) => {
    await page.route('**/api/v1/mvg/stations/search**', async route => {
      const url = new URL(route.request().url())
      const query = (url.searchParams.get('query') || '').toLowerCase()

      if (query.includes('mar')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [mockStation],
            meta: { total: 1 },
          }),
        })
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: { total: 0 } }),
      })
    })

    await page.route('**/api/v1/mvg/departures**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          station: mockStation,
          departures: [mockDeparture],
        }),
      })
    })

    await page.goto('/')

    const searchInput = page.getByPlaceholder('Search for a station')
    await searchInput.fill('Marienplatz')

    await page.getByRole('button', { name: /Marienplatz/ }).click()

    await expect(page).toHaveURL(/\/departures\/de:09162:1$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Marienplatz/)
    await expect(page.getByRole('table')).toContainText('U3')
    await expect(page.getByRole('table')).toContainText('Moosach')
  })

  test('user can open the planner view from navigation', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Planner' }).click()

    await expect(page).toHaveURL(/\/planner$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Route Planner')
    await expect(page.getByText(/Coming soon/i)).toBeVisible()
  })
})
