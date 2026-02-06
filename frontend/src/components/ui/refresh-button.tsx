import { Button, type ButtonProps } from './button'
import { Spinner } from './spinner'

interface RefreshButtonProps extends Omit<ButtonProps, 'onClick'> {
  onClick: () => void
  loading?: boolean
  loadingText?: string
  icon?: string
}

export function RefreshButton({
  onClick,
  disabled = false,
  loading = false,
  loadingText = 'Refreshing...',
  icon = '🔄',
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
        <>{children ?? `${icon} Refresh`}</>
      )}
    </Button>
  )
}
