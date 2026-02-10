import { RefreshCw } from 'lucide-react'
import { Button, type ButtonProps } from './button'
import { Spinner } from './spinner'

interface RefreshButtonProps extends Omit<ButtonProps, 'onClick'> {
  onClick: () => void
  loading?: boolean
  loadingText?: string
}

export function RefreshButton({
  onClick,
  disabled = false,
  loading = false,
  loadingText = 'Refreshing...',
  children,
  ...props
}: RefreshButtonProps) {
  return (
    <Button onClick={onClick} disabled={disabled || loading} {...props}>
      {loading ? (
        <>
          <Spinner />
          {loadingText}
        </>
      ) : (
        <>
          <RefreshCw aria-hidden="true" />
          {children ?? 'Refresh'}
        </>
      )}
    </Button>
  )
}
