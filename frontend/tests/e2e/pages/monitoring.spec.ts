/**
 * Monitoring Page E2E Tests
 * Tests for the system monitoring page with tabs
 */

import { test, expect } from '@playwright/test'
import { setupHealthMocks } from '../fixtures/mocks'

test.describe('Monitoring Page', () => {
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

    // Mock ingestion status endpoint
    await page.route('**/api/v1/system/ingestion-status**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          gtfs_feed: {
            feed_id: 'test-feed-123',
            feed_url: 'https://example.com/gtfs.zip',
            downloaded_at: '2025-01-01T00:00:00Z',
            feed_start_date: '2025-01-01',
            feed_end_date: '2025-12-31',
            stop_count: 5000,
            route_count: 200,
            trip_count: 25000,
            is_expired: false,
          },
          gtfs_rt_harvester: {
            is_running: true,
            last_harvest_at: '2025-01-01T12:00:00Z',
            stations_updated_last_harvest: 150,
            total_stats_records: 50000,
          },
        }),
      })
    })
  })

  test('loads monitoring page with header', async ({ page }) => {
    await page.goto('/monitoring')

    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible()
    await expect(page.getByText(/Real-time system health/)).toBeVisible()
  })

  test('displays tab navigation', async ({ page }) => {
    await page.goto('/monitoring')

    await expect(page.getByRole('button', { name: /Overview/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Ingestion/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Performance/ })).toBeVisible()
  })

  test('shows Overview tab by default', async ({ page }) => {
    await page.goto('/monitoring')

    // Overview content should be visible
    await expect(page.getByText(/All Systems Operational|System Issues/)).toBeVisible()
  })

  test('switches to Ingestion tab', async ({ page }) => {
    await page.goto('/monitoring')

    await page.getByRole('button', { name: /Ingestion/ }).click()

    await expect(page.getByText('GTFS Static Feed')).toBeVisible()
    await expect(page.getByText('Realtime Harvester')).toBeVisible()
  })

  test('shows feed record counts on Ingestion tab', async ({ page }) => {
    await page.goto('/monitoring')

    await page.getByRole('button', { name: /Ingestion/ }).click()

    await expect(page.getByText('5,000')).toBeVisible() // stop_count
    await expect(page.getByText('200')).toBeVisible() // route_count
    await expect(page.getByText('25,000')).toBeVisible() // trip_count
  })

  test('switches to Performance tab', async ({ page }) => {
    await page.goto('/monitoring')

    await page.getByRole('button', { name: /Performance/ }).click()

    await expect(page.getByText('Cache Performance')).toBeVisible()
    await expect(page.getByText('Performance Targets')).toBeVisible()
  })

  test('navigates to monitoring via nav link', async ({ page }) => {
    await page.goto('/')

    // Wait for heatmap to load
    await page.locator('[data-testid="heatmap-container"]').waitFor({ timeout: 10000 })

    const monitoringLink = page.getByRole('link', { name: 'Monitoring' })
    await monitoringLink.click()

    await expect(page).toHaveURL('/monitoring')
  })
})

test.describe('Monitoring Page - Error States', () => {
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
    await page.route('**/api/v1/system/ingestion-status**', async route => {
      return route.fulfill({ status: 500, body: 'Error' })
    })

    await page.goto('/monitoring')

    // Page still loads but may show error state
    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible()
  })

  test('handles ingestion status failure gracefully', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({ status: 200, contentType: 'text/plain', body: '' })
    })
    await page.route('**/api/v1/system/ingestion-status**', async route => {
      return route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'Service unavailable' }),
      })
    })

    await page.goto('/monitoring')
    await page.getByRole('button', { name: /Ingestion/ }).click()

    // Should show error state
    await expect(page.getByText(/Failed to load ingestion status/)).toBeVisible()
  })
})

test.describe('Monitoring Page - Refresh', () => {
  test('can manually refresh on Performance tab', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# HELP test\ntest_metric 100',
      })
    })

    await page.goto('/monitoring')
    await page.getByRole('button', { name: /Performance/ }).click()

    const refreshButton = page.getByRole('button', { name: /Refresh/ })
    await expect(refreshButton).toBeVisible()
    await refreshButton.click()

    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible()
  })

  test('can toggle auto-refresh on Performance tab', async ({ page }) => {
    await setupHealthMocks(page)
    await page.route('**/metrics**', async route => {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: '# Metrics',
      })
    })

    await page.goto('/monitoring')
    await page.getByRole('button', { name: /Performance/ }).click()

    const autoRefreshButton = page.getByRole('button', { name: /Auto-refreshing/ })
    await expect(autoRefreshButton).toBeVisible()

    await autoRefreshButton.click()

    await expect(page.getByRole('button', { name: /Manual refresh/ })).toBeVisible()
  })
})
