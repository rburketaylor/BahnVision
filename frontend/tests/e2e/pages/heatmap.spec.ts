/**
 * Heatmap Page E2E Tests
 * Tests for the landing page heatmap visualization
 */

import { test, expect } from '@playwright/test'
import {
  setupHeatmapMocks,
  setupStationMocks,
  mockHeatmapData,
  mockStationStats,
} from '../fixtures/mocks'

test.describe('Heatmap Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupHeatmapMocks(page)
    await setupStationMocks(page)
  })

  test('loads and displays the heatmap', async ({ page }) => {
    await page.goto('/')

    // Verify page container with data-testid
    await expect(page.locator('[data-testid="heatmap-container"]')).toBeVisible({
      timeout: 10000,
    })
  })

  test('displays heatmap controls panel', async ({ page }) => {
    await page.goto('/')

    // Look for the Heatmap title in the overlay panel
    await expect(page.getByText(/Heatmap/)).toBeVisible({ timeout: 10000 })
  })

  test('displays tips section', async ({ page }) => {
    await page.goto('/')

    // Tips section should be visible
    await expect(page.getByText('Tips')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/Click a station dot/)).toBeVisible()
  })

  test('displays data source attribution', async ({ page }) => {
    await page.goto('/')

    // Data source attribution should be visible
    await expect(page.getByText(/Data source/)).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('link', { name: 'gtfs.de' })).toBeVisible()
  })

  test('navigates to stations page via navigation', async ({ page }) => {
    await page.goto('/')

    // Click on Stations link in navigation (not "search")
    const stationsLink = page.getByRole('link', { name: 'Stations' })
    await stationsLink.click()

    await expect(page).toHaveURL('/search')
  })

  test('redirects /heatmap to /', async ({ page }) => {
    await page.goto('/heatmap')

    // Should redirect to root
    await expect(page).toHaveURL('/')
  })

  test('shows a station popup on first click and loads stats', async ({ page }) => {
    // Delay station stats slightly so we can observe the loading state.
    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      await new Promise(resolve => setTimeout(resolve, 300))
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStationStats),
      })
    })

    const overviewResponse = page.waitForResponse(
      resp => resp.url().includes('/api/v1/heatmap/overview'),
      { timeout: 15000 }
    )

    await page.goto('/')

    const canvas = page.locator('canvas.maplibregl-canvas')
    await expect(canvas).toBeVisible({ timeout: 15000 })

    await overviewResponse

    await page.waitForFunction(() => {
      const el = document.querySelector('canvas.maplibregl-canvas') as HTMLCanvasElement | null
      return Boolean(el && el.width > 0 && el.height > 0)
    })

    const statsResponse = page.waitForResponse(resp => {
      return resp.url().includes('/api/v1/transit/stops/') && resp.url().includes('/stats')
    })

    const box = await canvas.boundingBox()
    expect(box).toBeTruthy()

    // Clicking canvas coordinates is slightly flaky across browsers; try a small cluster of points.
    const popup = page.locator('.maplibregl-popup-content')
    const centerX = box!.width / 2
    const centerY = box!.height / 2
    const offsets = [
      [0, 0],
      [8, 0],
      [-8, 0],
      [0, 8],
      [0, -8],
    ] as const

    for (const [dx, dy] of offsets) {
      await canvas.click({ position: { x: centerX + dx, y: centerY + dy } })
      if (await popup.isVisible()) break
    }

    await expect(popup).toBeVisible({ timeout: 10000 })
    await expect(popup).toContainText(mockStationStats.station_name)
    await expect(popup).toContainText('Loading details...')

    await statsResponse
    await expect(popup).toContainText('Departures', { timeout: 10000 })
  })
})

test.describe('Heatmap Error States', () => {
  test('shows error state when heatmap API fails', async ({ page }) => {
    await page.route('**/api/v1/heatmap**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/')

    // Should display error message from the overlay
    await expect(page.getByText(/Failed to load heatmap data/)).toBeVisible({ timeout: 10000 })
  })

  test('page loads successfully with delayed API response', async ({ page }) => {
    // Delay the response to see that page still loads
    await page.route('**/api/v1/heatmap**', async route => {
      await new Promise(resolve => setTimeout(resolve, 500))
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockHeatmapData),
      })
    })

    await page.goto('/')

    // Page should eventually display the container
    await expect(page.locator('[data-testid="heatmap-container"]')).toBeVisible({ timeout: 15000 })
  })
})
