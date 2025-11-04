/**
 * Main App component with routing configuration
 */

import { BrowserRouter, Routes, Route } from 'react-router'
import Layout from './components/Layout'
import { MainPage } from './pages/MainPage'
import { DeparturesPage } from './pages/DeparturesPage'
import PlannerPage from './pages/PlannerPage'
import InsightsPage from './pages/InsightsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<MainPage />} />
          <Route path="/departures/:stationId" element={<DeparturesPage />} />
          <Route path="/planner" element={<PlannerPage />} />
          <Route path="/insights" element={<InsightsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
