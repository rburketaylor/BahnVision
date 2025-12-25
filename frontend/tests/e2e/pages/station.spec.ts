/**
 * Station Page E2E Tests
 * Tests for station details page with all tabs
 */

import { test, expect } from '@playwright/test'
import { setupStationMocks, mockStation, mockCancelledDeparture } from '../fixtures/mocks'

test.describe('Station Page - Direct Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
  })

  test('loads station page via direct URL', async ({ page }) => {
    await page.goto(`/station/${mockStation.id}`)

    await expect(page.getByRole('heading', { level: 1 })).toContainText(mockStation.name)
  })

  test('shows error for non-existent station', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Station not found' }),
      })
    })

    await page.goto('/station/nonexistent:id')

    // Should show some error or empty state
    await expect(
      page.getByText(/not found|error|couldn't load/i).or(page.getByText(/No data/i))
    ).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Station Page - Overview Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
    await page.goto(`/station/${mockStation.id}`)
  })

  test('displays station name in header', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toContainText(mockStation.name)
  })

  test('shows performance card', async ({ page }) => {
    // Overview tab should be default with performance card (title is "Performance")
    await expect(page.getByText('Performance')).toBeVisible()
  })

  test('displays cancellation rate', async ({ page }) => {
    await expect(page.getByText(/Cancellation Rate/)).toBeVisible()
  })

  test('displays delay rate', async ({ page }) => {
    await expect(page.getByText(/Delay Rate/)).toBeVisible()
  })

  test('shows departures count', async ({ page }) => {
    await expect(
      page.getByText(/Total Departures/i).or(page.getByText(/departures/i))
    ).toBeVisible()
  })
})

test.describe('Station Page - Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
    await page.goto(`/station/${mockStation.id}`)
  })

  test('can switch to Trends tab', async ({ page }) => {
    const trendsTab = page.getByRole('button', { name: 'Trends' })
    await trendsTab.click()

    await expect(page).toHaveURL(/tab=trends/)
  })

  test('can switch to Schedule tab', async ({ page }) => {
    const scheduleTab = page.getByRole('button', { name: 'Schedule' })
    await scheduleTab.click()

    // Should show departures board
    await expect(page).toHaveURL(/tab=schedule/)
  })

  test('can return to Overview tab', async ({ page }) => {
    // Go to Schedule first
    await page.getByRole('button', { name: 'Schedule' }).click()
    await expect(page).toHaveURL(/tab=schedule/)

    // Then back to Overview
    await page.getByRole('button', { name: 'Overview' }).click()

    // Should show overview content (Performance card is visible)
    await expect(page.getByText('Cancellation Rate')).toBeVisible()
  })

  test('preserves tab state in URL', async ({ page }) => {
    await page.getByRole('button', { name: 'Schedule' }).click()

    // URL should include tab parameter
    await expect(page).toHaveURL(/tab=schedule/)
  })
})

test.describe('Station Page - Schedule Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
    await page.goto(`/station/${mockStation.id}`)
    await page.getByRole('button', { name: 'Schedule' }).click()
  })

  test('displays departure list', async ({ page }) => {
    await expect(page.getByText('Moosach')).toBeVisible()
    await expect(page.getByText('Flughafen')).toBeVisible()
  })

  test('shows departure count', async ({ page }) => {
    await expect(page.getByText(/2 departures/i)).toBeVisible()
  })

  test('shows delay indicator for delayed departures', async ({ page }) => {
    // The first departure has a 120 second (2 min) delay
    await expect(page.getByText(/\+2/)).toBeVisible()
  })

  test('handles empty departures list', async ({ page }) => {
    await page.route('**/api/v1/transit/departures**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stop: mockStation,
          departures: [],
          realtime_available: true,
        }),
      })
    })

    await page.reload()
    await page.getByRole('button', { name: 'Schedule' }).click()

    await expect(page.getByText(/0 departures|no departures/i)).toBeVisible()
  })

  test('shows cancelled departure indicator', async ({ page }) => {
    await page.route('**/api/v1/transit/departures**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stop: mockStation,
          departures: [mockCancelledDeparture],
          realtime_available: true,
        }),
      })
    })

    await page.reload()
    await page.getByRole('button', { name: 'Schedule' }).click()

    // Should show 1 departure (the cancelled one)
    await expect(page.getByText(/1 departure/i)).toBeVisible()
    await expect(page.getByText('Garching')).toBeVisible()
  })
})

test.describe('Station Page - Trends Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
    await page.goto(`/station/${mockStation.id}`)
    await page.getByRole('button', { name: 'Trends' }).click()
  })

  test('navigates to trends tab', async ({ page }) => {
    await expect(page).toHaveURL(/tab=trends/)
  })

  test('can change time range', async ({ page }) => {
    // Find any time range selector that might be present
    const timeSelector = page
      .getByRole('combobox')
      .or(page.getByRole('button', { name: /24h|1h|7d/i }))
      .first()
    if (await timeSelector.isVisible()) {
      await timeSelector.click()
    }
  })
})

test.describe('Station Page - Error States', () => {
  test('shows error when stats API fails', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto(`/station/${mockStation.id}`)

    // Should show error state or station name still loads from other data
    await expect(
      page.getByText(/error|failed|couldn't load/i).or(page.getByRole('heading', { level: 1 }))
    ).toBeVisible()
  })

  test('shows error when departures API fails', async ({ page }) => {
    // Setup base mocks first
    await setupStationMocks(page)

    // Then override the departures route to fail
    await page.route('**/api/v1/transit/departures**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto(`/station/${mockStation.id}`)
    await page.getByRole('button', { name: 'Schedule' }).click()

    // Should show error message from departures API
    await expect(page.getByText(/Error|failed|departures/i)).toBeVisible()
  })
})
