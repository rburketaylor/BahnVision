/**
 * User Journey E2E Tests
 * Cross-page flows that test complete user scenarios
 */

import { test, expect } from '@playwright/test'
import {
  setupStationMocks,
  setupHeatmapMocks,
  setupHealthMocks,
  mockStation,
} from '../fixtures/mocks'

test.describe('Complete User Journeys', () => {
  test.beforeEach(async ({ page }) => {
    await setupHeatmapMocks(page)
    await setupStationMocks(page)
    await setupHealthMocks(page)

    // Also mock metrics for monitoring page
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# Metrics\ntest_metric 1',
      })
    })
  })

  test('user can navigate from heatmap to station details', async ({ page }) => {
    // Start at landing page
    await page.goto('/')
    await expect(page.locator('[data-testid="heatmap-container"]')).toBeVisible({ timeout: 10000 })

    // Navigate to stations (search) page via nav
    await page.getByRole('link', { name: 'Stations' }).click()
    await expect(page).toHaveURL('/search')

    // Search for a station
    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Marienplatz')

    // Select the station
    await page.getByRole('button', { name: /Marienplatz/i }).click()

    // Verify we're on the station page
    await expect(page).toHaveURL(new RegExp(`/station/${mockStation.id}`))
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Marienplatz')
  })

  test('user can explore all station tabs and return home', async ({ page }) => {
    await page.goto(`/station/${mockStation.id}`)

    // Wait for station page to load
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

    // Overview tab (default) - shows stat cards
    await expect(page.getByText('Cancellation Rate')).toBeVisible()

    // Switch to Trends
    await page.getByRole('button', { name: 'Trends' }).click()
    await expect(page).toHaveURL(/tab=trends/)

    // Switch to Schedule
    await page.getByRole('button', { name: 'Schedule' }).click()
    await expect(page).toHaveURL(/tab=schedule/)
    await expect(page.getByText('Moosach')).toBeVisible()

    // Navigate back to stations page
    await page.getByRole('link', { name: 'Stations' }).click()
    await expect(page).toHaveURL('/search')

    // Navigate to home (Map) - use exact match to avoid "Back to Map" link
    await page.getByRole('link', { name: 'Map', exact: true }).click()
    await expect(page).toHaveURL('/')
  })

  test('user can check system monitoring after viewing stations', async ({ page }) => {
    // View a station first
    await page.goto(`/station/${mockStation.id}`)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Marienplatz')

    // Navigate to monitoring
    await page.getByRole('link', { name: 'Monitoring' }).click()
    await expect(page).toHaveURL('/monitoring')
    await expect(page.getByText('System Monitoring')).toBeVisible()
  })

  test('user can search multiple stations in sequence', async ({ page }) => {
    await page.goto('/search')

    // Search for first station
    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Marienplatz')
    await page.getByRole('button', { name: /Marienplatz/i }).click()
    await expect(page).toHaveURL(new RegExp(`/station/${mockStation.id}`))

    // Go back and search for another
    await page.getByRole('link', { name: 'Stations' }).click()
    await searchInput.fill('Haupt')
    await page.getByRole('button', { name: /Hauptbahnhof/i }).click()
    await expect(page).toHaveURL(/\/station\/de:09162:2/)
  })
})

test.describe('Navigation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupHeatmapMocks(page)
    await setupStationMocks(page)
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# Metrics',
      })
    })
  })

  test('browser back button works correctly', async ({ page }) => {
    await page.goto('/')
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    await page.getByRole('link', { name: 'Stations' }).click()
    await expect(page).toHaveURL('/search')

    await page.getByRole('link', { name: 'Monitoring' }).click()
    await expect(page).toHaveURL('/monitoring')

    // Go back
    await page.goBack()
    await expect(page).toHaveURL('/search')

    // Go back again
    await page.goBack()
    await expect(page).toHaveURL('/')
  })

  test('browser forward button works correctly', async ({ page }) => {
    await page.goto('/')
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    await page.getByRole('link', { name: 'Stations' }).click()
    await expect(page).toHaveURL('/search')

    // Go back then forward
    await page.goBack()
    await expect(page).toHaveURL('/')

    await page.goForward()
    await expect(page).toHaveURL('/search')
  })

  test('direct URL navigation works for all pages', async ({ page }) => {
    // Test each route directly
    await page.goto('/')
    await expect(page.locator('[data-testid="heatmap-container"]')).toBeVisible({ timeout: 10000 })

    await page.goto('/search')
    await expect(page.getByRole('combobox', { name: /station search/i })).toBeVisible()

    await page.goto(`/station/${mockStation.id}`)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Marienplatz')

    await page.goto('/monitoring')
    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible()
  })
})

test.describe('Theme Toggle', () => {
  test.beforeEach(async ({ page }) => {
    await setupHeatmapMocks(page)
  })

  test('can toggle between light and dark themes', async ({ page }) => {
    await page.goto('/')
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    // Find theme toggle button (it has aria-label "Toggle theme")
    const themeToggle = page.getByRole('button', { name: /toggle theme/i })
    if (await themeToggle.isVisible()) {
      // Get initial theme
      const htmlElement = page.locator('html')
      const initialClass = await htmlElement.getAttribute('class')

      // Toggle theme
      await themeToggle.click()

      // Class should change (dark/light)
      const newClass = await htmlElement.getAttribute('class')
      expect(newClass).not.toBe(initialClass)
    }
  })

  test('theme preference persists across page navigation', async ({ page }) => {
    await setupStationMocks(page)
    await page.goto('/')
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    const themeToggle = page.getByRole('button', { name: /toggle theme/i })
    if (await themeToggle.isVisible()) {
      await themeToggle.click()

      const htmlElement = page.locator('html')
      const themeAfterToggle = await htmlElement.getAttribute('class')

      // Navigate to another page
      await page.goto('/search')

      // Theme should persist
      const themeAfterNav = await htmlElement.getAttribute('class')
      expect(themeAfterNav).toBe(themeAfterToggle)
    }
  })
})
