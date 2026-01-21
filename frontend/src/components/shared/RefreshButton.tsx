/**
 * RefreshButton
 * A button component for refresh actions with loading state
 */

import { Spinner } from './Spinner'

interface RefreshButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  loadingText?: string
  icon?: string
  className?: string
}

export function RefreshButton({
  onClick,
  disabled = false,
  loading = false,
  loadingText = 'Refreshing...',
  icon = '🔄',
  className = '',
}: RefreshButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2 ${className}`}
    >
      {loading ? (
        <>
          <Spinner />
          {loadingText}
        </>
      ) : (
        <>{icon} Refresh</>
      )}
    </button>
  )
}
