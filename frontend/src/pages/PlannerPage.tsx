/**
 * Route Planner Page
 * Plan journeys between two stations
 *
 * NOTE: Route planning is not yet implemented in the GTFS API.
 * This page shows a "Coming Soon" placeholder.
 */

import { Link } from 'react-router'

export default function PlannerPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground">Route Planner</h1>
        <p className="text-gray-400 mt-2">
          Plan your journey across Germany's public transport network
        </p>
      </header>

      <div className="bg-card rounded-lg border border-border p-8 shadow-sm text-center">
        <div className="text-6xl mb-6">🚧</div>
        <h2 className="text-2xl font-semibold text-foreground mb-4">Coming Soon</h2>
        <p className="text-gray-500 mb-6 max-w-md mx-auto">
          Route planning functionality is being developed as part of our GTFS migration. This
          feature will enable journey planning across Germany's public transport network.
        </p>

        <div className="space-y-3">
          <p className="text-sm text-gray-400">In the meantime, you can:</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/"
              className="inline-flex items-center justify-center px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors"
            >
              Search for Stops
            </Link>
            <Link
              to="/heatmap"
              className="inline-flex items-center justify-center px-4 py-2 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80 transition-colors"
            >
              View Heatmap
            </Link>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-border">
          <h3 className="text-sm font-medium text-foreground mb-3">Planned Features:</h3>
          <ul className="text-sm text-gray-500 space-y-2">
            <li>✓ Multi-modal journey planning</li>
            <li>✓ Real-time delay integration</li>
            <li>✓ Alternative route suggestions</li>
            <li>✓ Accessibility options</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
