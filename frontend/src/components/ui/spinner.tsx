import { cn } from '@/lib/utils'

interface SpinnerProps {
  className?: string
}

export function Spinner({ className }: SpinnerProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block h-4 w-4 animate-spin rounded-full border border-current border-t-transparent',
        className
      )}
    />
  )
}
