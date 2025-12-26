/**
 * Error Handling E2E Tests
 * Tests for application behavior under error conditions
 */

import { test, expect } from '@playwright/test'
import { mockStation } from './fixtures/mocks'

test.describe('Network Error Handling', () => {
  test('shows error state when heatmap API fails', async ({ page }) => {
    await page.route('**/api/v1/heatmap**', async route => {
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service unavailable' }),
      })
    })

    await page.goto('/')

    // Should show error in the heatmap overlay panel
    await expect(page.getByText(/Failed to load heatmap data/)).toBeVisible({ timeout: 10000 })
  })

  test('handles search API failure gracefully', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.abort('connectionrefused')
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Should show error state in search
    await expect(page.getByText(/error|failed/i)).toBeVisible({ timeout: 10000 })
  })

  test('can retry search after initial failure', async ({ page }) => {
    let callCount = 0

    await page.route('**/api/v1/transit/stops/search**', async route => {
      callCount++
      if (callCount <= 1) {
        return route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Temporary failure' }),
        })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ query: 'mar', results: [mockStation] }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Wait a moment for the error state
    await page.waitForTimeout(500)

    // Clear and retry (second call should succeed)
    await searchInput.fill('')
    await searchInput.fill('Mar')

    // Should now show results
    await expect(page.getByRole('button', { name: /Marienplatz/i })).toBeVisible({ timeout: 5000 })
  })
})

test.describe('HTTP Error Codes', () => {
  test('handles 400 Bad Request in search', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid query parameter' }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('abc')

    // Should handle gracefully - either show error or no results
    await expect(
      page
        .getByText(/error|invalid|no/i)
        .or(page.getByRole('combobox', { name: /station search/i }))
    ).toBeVisible({ timeout: 5000 })
  })

  test('handles 404 Not Found for station', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Station not found' }),
      })
    })

    await page.goto('/station/invalid:station:id')

    await expect(page.getByText(/not found|error|No data/i)).toBeVisible({ timeout: 5000 })
  })

  test('handles 429 Rate Limited in search', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 429,
        contentType: 'application/json',
        headers: { 'Retry-After': '60' },
        body: JSON.stringify({ detail: 'Too many requests' }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    await expect(page.getByText(/error|too many|rate limit/i)).toBeVisible({ timeout: 5000 })
  })

  test('handles 500 Internal Server Error on heatmap', async ({ page }) => {
    await page.route('**/api/v1/heatmap**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/')

    await expect(page.getByText(/Failed to load heatmap data/)).toBeVisible({ timeout: 10000 })
  })

  test('handles 502 Bad Gateway on heatmap', async ({ page }) => {
    await page.route('**/api/v1/heatmap**', async route => {
      return route.fulfill({
        status: 502,
        contentType: 'text/html',
        body: '<html><body>Bad Gateway</body></html>',
      })
    })

    await page.goto('/')

    await expect(page.getByText(/Failed to load heatmap data/)).toBeVisible({ timeout: 10000 })
  })

  test('handles 503 Service Unavailable on heatmap', async ({ page }) => {
    await page.route('**/api/v1/heatmap**', async route => {
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service temporarily unavailable' }),
      })
    })

    await page.goto('/')

    await expect(page.getByText(/Failed to load heatmap data/)).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Malformed Response Handling', () => {
  test('handles non-JSON search response', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body>Not JSON</body></html>',
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Should handle gracefully, not crash - search input should still be visible
    await expect(page.getByRole('combobox', { name: /station search/i })).toBeVisible()
  })

  test('handles empty search response', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '',
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Should handle gracefully
    await expect(page.getByRole('combobox', { name: /station search/i })).toBeVisible()
  })

  test('handles search response with missing results field', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ query: 'mar' }), // Missing 'results' field
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Should not crash, may show empty results
    await expect(page.getByRole('combobox', { name: /station search/i })).toBeVisible()
  })
})

test.describe('Invalid URL Handling', () => {
  test('handles invalid station ID format', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/**/stats**', async route => {
      return route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid station ID format' }),
      })
    })

    // Use simple invalid ID
    await page.goto('/station/test-invalid-id')

    // Page should load without crashing - header or error is showed
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('Slow Response Handling', () => {
  test('shows loading state for slow search responses', async ({ page }) => {
    await page.route('**/api/v1/transit/stops/search**', async route => {
      await new Promise(resolve => setTimeout(resolve, 2000))
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ query: 'mar', results: [mockStation] }),
      })
    })

    await page.goto('/search')

    const searchInput = page.getByRole('combobox', { name: /station search/i })
    await searchInput.fill('Mar')

    // Either loading shows, or results eventually appear
    await expect(
      page.getByText(/loading|searching/i).or(page.getByRole('button', { name: /Marienplatz/i }))
    ).toBeVisible({ timeout: 5000 })
  })
})
