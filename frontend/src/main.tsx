/**
 * Application entry point
 * Sets up React Query and Sentry providers
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/query-client'
import App from './App'
import './index.css'
// Import Leaflet CSS globally to ensure it's loaded before any map components
import 'leaflet/dist/leaflet.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
