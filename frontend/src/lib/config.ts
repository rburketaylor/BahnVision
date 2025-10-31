/**
 * Application configuration
 * Sources environment variables via Vite's import.meta.env
 */

interface Config {
  apiBaseUrl: string
  sentryDsn: string | undefined
  enableDebugLogs: boolean
  mapTileUrl: string
  mapAttribution: string
  environment: 'development' | 'production' | 'test'
}

export const config: Config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  sentryDsn: import.meta.env.VITE_SENTRY_DSN,
  enableDebugLogs: import.meta.env.VITE_ENABLE_DEBUG_LOGS === 'true',
  mapTileUrl:
    import.meta.env.VITE_MAP_TILE_URL ||
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  mapAttribution:
    import.meta.env.VITE_MAP_ATTRIBUTION ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  environment: (import.meta.env.MODE as Config['environment']) || 'development',
}

// Validate required configuration
if (!config.apiBaseUrl) {
  throw new Error('VITE_API_BASE_URL environment variable is required')
}
