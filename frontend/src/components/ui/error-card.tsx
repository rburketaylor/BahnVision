import { Alert, AlertDescription, AlertTitle } from './alert'
import { Button } from './button'

interface ErrorCardProps {
  title: string
  message: string
  onRetry?: () => void
  retryText?: string
}

export function ErrorCard({ title, message, onRetry, retryText = 'Retry' }: ErrorCardProps) {
  return (
    <Alert
      variant="destructive"
      className="border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl" aria-hidden="true">
          🚨
        </span>
        <div>
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{message}</AlertDescription>
        </div>
      </div>
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          onClick={onRetry}
          className="mt-4 border-red-300 bg-red-100 text-red-800 hover:bg-red-200 dark:border-red-700 dark:bg-red-800 dark:text-red-100 dark:hover:bg-red-700"
        >
          {retryText}
        </Button>
      )}
    </Alert>
  )
}
