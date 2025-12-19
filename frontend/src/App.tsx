/**
 * Main App component with routing configuration
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { ThemeProvider } from './contexts/ThemeContext'
import Layout from './components/Layout'
import { MainPage } from './pages/MainPage'
import { StationPage } from './pages/StationPage'
import InsightsPage from './pages/InsightsPage'
import HeatmapPage from './pages/HeatmapPage'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            {/* Heatmap is the new landing page */}
            <Route path="/" element={<HeatmapPage />} />
            <Route path="/heatmap" element={<Navigate to="/" replace />} />
            {/* Station search page */}
            <Route path="/search" element={<MainPage />} />
            {/* Station details page with tabs */}
            <Route path="/station/:stationId" element={<StationPage />} />
            {/* Insights page */}
            <Route path="/insights" element={<InsightsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
