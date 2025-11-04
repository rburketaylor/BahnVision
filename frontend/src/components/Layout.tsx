/**
 * Main layout component with navigation
 */

import { Link, Outlet, useLocation } from 'react-router'

export default function Layout() {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Departures' },
    { path: '/planner', label: 'Planner' },
    { path: '/insights', label: 'Insights' },
  ]

  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="bg-card shadow-sm border-b border-border">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-8">
              <Link to="/" className="text-xl font-bold text-primary">
                BahnVision
              </Link>
              <div className="hidden md:flex space-x-4">
                {navItems.map(item => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      location.pathname === item.path
                        ? 'bg-primary/10 text-primary'
                        : 'text-gray-400 hover:text-primary hover:bg-gray-700'
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
