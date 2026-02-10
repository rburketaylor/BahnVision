import { defineConfig, devices } from '@playwright/test'

const shouldStartWebServer =
  process.env.PLAYWRIGHT_START_WEB_SERVER === '1' ||
  (!process.env.CI && process.env.PLAYWRIGHT_BASE_URL == null)

const baseURL =
  process.env.PLAYWRIGHT_BASE_URL ??
  (shouldStartWebServer ? 'http://localhost:5173' : 'http://localhost:3000')

export default defineConfig({
  testDir: './tests/e2e',
  tsconfig: './tsconfig.playwright.json',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    ...(process.env.CI || process.env.PLAYWRIGHT_INCLUDE_WEBKIT === '1'
      ? [
          {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
          },
        ]
      : []),
  ],
  webServer: shouldStartWebServer
    ? {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
      }
    : undefined,
})
