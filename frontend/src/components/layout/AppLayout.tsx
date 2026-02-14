/**
 * Main layout shell with responsive navigation.
 */

import { useEffect, useState, type ComponentType } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { Activity, Map, Menu, Search, X } from 'lucide-react'
import { Button } from '../ui/button'
import { ThemeToggle } from './ThemeToggle'

interface NavItem {
  path: string
  label: string
  icon: ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { path: '/', label: 'Map', icon: Map },
  { path: '/search', label: 'Stations', icon: Search },
  { path: '/monitoring', label: 'Monitoring', icon: Activity },
]

function NavEntry({
  item,
  mobile = false,
  onClick,
}: {
  item: NavItem
  mobile?: boolean
  onClick?: () => void
}) {
  const Icon = item.icon

  return (
    <NavLink
      to={item.path}
      onClick={onClick}
      className={({ isActive }) =>
        `inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150 ${
          mobile ? 'w-full' : ''
        } ${
          isActive
            ? 'bg-primary/12 text-primary border border-primary/25 shadow-sm'
            : 'text-muted-foreground hover:bg-surface-elevated hover:text-foreground border border-transparent'
        }`
      }
      end={item.path === '/'}
    >
      <Icon className="h-4 w-4" />
      {item.label}
    </NavLink>
  )
}

export default function AppLayout() {
  const location = useLocation()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const isFullBleed = location.pathname === '/' || location.pathname === '/heatmap'

  useEffect(() => {
    setIsMobileMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-[2000] border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[116rem] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-8">
            <Link to="/" className="inline-flex items-center gap-2">
              <span className="font-display text-[1.2rem] font-semibold uppercase tracking-[0.16em] text-foreground">
                BahnVision
              </span>
            </Link>

            <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
              {navItems.map(item => (
                <NavEntry key={item.path} item={item} />
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsMobileMenuOpen(open => !open)}
              className="md:hidden"
              aria-label="Toggle navigation menu"
            >
              {isMobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {isMobileMenuOpen && (
          <div className="animate-slide-down border-t border-border/60 bg-surface/95 px-4 py-3 md:hidden sm:px-6">
            <nav className="flex flex-col gap-2" aria-label="Mobile navigation">
              {navItems.map(item => (
                <NavEntry
                  key={item.path}
                  item={item}
                  mobile
                  onClick={() => setIsMobileMenuOpen(false)}
                />
              ))}
            </nav>
          </div>
        )}
      </header>

      <main
        className={isFullBleed ? '' : 'mx-auto w-full max-w-[116rem] px-4 py-8 sm:px-6 lg:px-8'}
      >
        <Outlet />
      </main>
    </div>
  )
}
