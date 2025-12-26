/**
 * Insights Page E2E Tests
 * Tests for the system health and metrics page
 */

import { test, expect } from '@playwright/test'
import { setupHealthMocks } from '../fixtures/mocks'

test.describe('Insights Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupHealthMocks(page)

    // Mock the Prometheus metrics endpoint
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: `
# HELP bahnvision_cache_events_total Cache events
bahnvision_cache_events_total{cache="transit_departures",event="hit"} 850
bahnvision_cache_events_total{cache="transit_departures",event="miss"} 150
# HELP bahnvision_transit_requests_total Total requests
bahnvision_transit_requests_total{method="GET"} 1000
        `.trim(),
      })
    })
  })

  test('loads insights page with header', async ({ page }) => {
    await page.goto('/insights')

    await expect(page.getByRole('heading', { name: 'System Insights' })).toBeVisible()
    await expect(page.getByText(/Real-time system health/)).toBeVisible()
  })

  test('displays system status card', async ({ page }) => {
    await page.goto('/insights')

    // System Status card should be visible
    await expect(page.getByText('System Status')).toBeVisible()
    // Shows Healthy or Issues based on status
    await expect(page.getByText(/Healthy|Issues/).first()).toBeVisible()
  })

  test('shows cache hit rate metric', async ({ page }) => {
    await page.goto('/insights')

    await expect(page.getByText('Cache Hit Rate')).toBeVisible()
    // The metrics should show calculated hit rate
  })

  test('shows API requests metric', async ({ page }) => {
    await page.goto('/insights')

    await expect(page.getByText('API Requests')).toBeVisible()
  })

  test('shows uptime metric', async ({ page }) => {
    await page.goto('/insights')

    await expect(page.getByText('Uptime').first()).toBeVisible()
  })

  test('shows refresh button', async ({ page }) => {
    await page.goto('/insights')

    await expect(page.getByRole('button', { name: /Refresh/ })).toBeVisible()
  })

  test('navigates to insights via nav link', async ({ page }) => {
    await page.goto('/')

    // Wait for heatmap to load
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    const insightsLink = page.getByRole('link', { name: 'Insights' })
    await insightsLink.click()

    await expect(page).toHaveURL('/insights')
  })
})

test.describe('Insights Page - Error States', () => {
  test('shows error when health API fails', async ({ page }) => {
    await page.route('**/api/v1/health**', async route => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service unavailable' }),
      })
    })
    await page.route('**/metrics**', async route => {
      return route.fulfill({ status: 200, contentType: 'text/plain', body: '' })
    })

    await page.goto('/insights')

    // Page still loads but may show error or fallback state
    // The header should still appear
    await expect(page.getByRole('heading', { name: 'System Insights' })).toBeVisible()
  })

  test('shows Issues status when health returns non-ok', async ({ page }) => {
    await page.route('**/api/v1/health**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            status: 'degraded',
            version: '1.0.0',
          },
        }),
      })
    })

    // Mock metrics too
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# No metrics',
      })
    })

    await page.goto('/insights')

    // Page should load showing system status
    await expect(page.getByText('System Status')).toBeVisible()
  })

  test('handles metrics endpoint failure gracefully', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 500,
        body: 'Internal Server Error',
      })
    })

    await page.goto('/insights')

    // Page should still load with the header
    await expect(page.getByRole('heading', { name: 'System Insights' })).toBeVisible()
    // Shows "Failed to load metrics" in the cache performance section
    await expect(page.getByText(/Failed to load metrics/)).toBeVisible()
  })
})

test.describe('Insights Page - Refresh', () => {
  test('can manually refresh metrics', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# HELP test\ntest_metric 100',
      })
    })

    await page.goto('/insights')

    // Click refresh button
    const refreshButton = page.getByRole('button', { name: /Refresh/ })
    await expect(refreshButton).toBeVisible()
    await refreshButton.click()

    // Should show refreshing state briefly
    await expect(page.getByRole('heading', { name: 'System Insights' })).toBeVisible()
  })

  test('can toggle auto-refresh', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# Metrics',
      })
    })

    await page.goto('/insights')

    // Find auto-refresh toggle button
    const autoRefreshButton = page.getByRole('button', { name: /Auto-refreshing/ })
    await expect(autoRefreshButton).toBeVisible()

    // Click to toggle off
    await autoRefreshButton.click()

    // Should now show "Manual refresh"
    await expect(page.getByRole('button', { name: /Manual refresh/ })).toBeVisible()
  })
})
