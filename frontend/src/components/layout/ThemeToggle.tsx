/**
 * Theme toggle control using token-driven icon button styling.
 */

import { MoonStar, Sun } from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'

export function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme()

  return (
    <button
      onClick={toggleTheme}
      className="btn-bvv inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-elevated text-muted-foreground hover:border-interactive/40 hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      aria-label={`Switch to ${resolvedTheme === 'light' ? 'dark' : 'light'} mode`}
      title={`Switch to ${resolvedTheme === 'light' ? 'dark' : 'light'} mode`}
      type="button"
    >
      {resolvedTheme === 'light' ? <MoonStar className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  )
}
