/**
 * Application entry point
 * Sets up React Query and Sentry providers
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/query-client'
import App from './App'
import './styles/globals.css'
import './styles/theme.css'
import './styles/map.css'
import './styles/animations.css'
// Import MapLibre GL CSS globally
import 'maplibre-gl/dist/maplibre-gl.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
