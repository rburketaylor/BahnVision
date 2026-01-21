/**
 * Spinner
 * A loading spinner component for indicating async operations
 */

interface SpinnerProps {
  className?: string
}

export function Spinner({ className = '' }: SpinnerProps) {
  return (
    <span
      className={`h-4 w-4 animate-spin rounded-full border border-current border-t-transparent ${className}`}
    />
  )
}
