/**
 * Search Page E2E Tests
 * Tests for the station search functionality
 */

import { test, expect } from '@playwright/test'
import { setupStationMocks, mockStation } from '../fixtures/mocks'

test.describe('Search Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupStationMocks(page)
  })

  test('displays search page with input', async ({ page }) => {
    await page.goto('/search')

    await expect(page.getByRole('heading', { name: /Command Search/i })).toBeVisible()
    await expect(page.getByRole('combobox', { name: /station search/i })).toBeVisible()
  })

  test('shows search results when typing', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    await expect(page.getByRole('button', { name: /Marienplatz/i })).toBeVisible()
  })

  test('shows empty state for no results', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('xyznonexistent')

    // Should show no results message or empty list
    await expect(page.getByText(/no results|no stations|not found/i)).toBeVisible()
  })

  test('navigates to station page on result click', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Marienplatz')

    await page.getByRole('button', { name: /Marienplatz/i }).click()

    await expect(page).toHaveURL(new RegExp(`/station/${mockStation.id}`))
  })

  test('clears search on escape key', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    await expect(page.getByRole('button', { name: /Marienplatz/i })).toBeVisible()

    await searchInput.press('Escape')

    // Results should be hidden
    await expect(page.getByRole('button', { name: /Marienplatz/i })).not.toBeVisible()
  })

  test('supports keyboard navigation in results', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    await expect(page.getByRole('button', { name: /Marienplatz/i })).toBeVisible()

    // Press down to highlight first result
    await searchInput.press('ArrowDown')
    await searchInput.press('Enter')

    await expect(page).toHaveURL(new RegExp(`/station/${mockStation.id}`))
  })
})

test.describe('Search Page - Error Handling', () => {
  test('shows error when search API fails', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    await expect(page.getByText(/error|failed/i)).toBeVisible()
  })

  test('handles network timeout gracefully', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      await new Promise(resolve => setTimeout(resolve, 30000)) // Long timeout
      return route.abort('timedout')
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Should show loading or eventually error state
    const loadingOrError = page.getByText(/loading|searching/i).or(page.getByText(/error|timeout/i))
    await expect(loadingOrError).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Search Page - Quick Links', () => {
  test('displays feature cards', async ({ page }) => {
    await page.goto('/search')

    await expect(page.getByText('Live Departures', { exact: true })).toBeVisible()
    await expect(page.getByText('Trend Analysis', { exact: true })).toBeVisible()
    await expect(page.getByText('Operations Visibility', { exact: true })).toBeVisible()
  })
})
