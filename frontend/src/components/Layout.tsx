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
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
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
                        : 'text-gray-600 hover:text-primary hover:bg-gray-50'
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

      <main>
        <Outlet />
      </main>
    </div>
  )
}
