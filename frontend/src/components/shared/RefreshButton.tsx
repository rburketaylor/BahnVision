/**
 * RefreshButton
 * Wrapper for refresh actions with consistent defaults.
 */

import { cn } from '@/lib/utils'
import { RefreshButton as UiRefreshButton } from '../ui/refresh-button'

interface RefreshButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  loadingText?: string
  className?: string
}

export function RefreshButton({
  onClick,
  disabled = false,
  loading = false,
  loadingText = 'Refreshing...',
  className = '',
}: RefreshButtonProps) {
  return (
    <UiRefreshButton
      onClick={onClick}
      disabled={disabled}
      loading={loading}
      loadingText={loadingText}
      className={cn('rounded-md', className)}
    >
      Refresh
    </UiRefreshButton>
  )
}
