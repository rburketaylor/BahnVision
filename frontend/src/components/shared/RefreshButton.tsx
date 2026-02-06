/**
 * RefreshButton
 * A button component for refresh actions with loading state
 */

import { cn } from '@/lib/utils'
import { RefreshButton as UiRefreshButton } from '../ui/refresh-button'

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
    <UiRefreshButton
      onClick={onClick}
      disabled={disabled}
      loading={loading}
      loadingText={loadingText}
      icon={icon}
      className={cn('rounded-lg', className)}
    >
      {icon} Refresh
    </UiRefreshButton>
  )
}
