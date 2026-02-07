import { AlertTriangle } from 'lucide-react'
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
      className="border-destructive/30 bg-destructive/10 text-destructive"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div>
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription className="text-destructive/90">{message}</AlertDescription>
        </div>
      </div>
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          onClick={onRetry}
          className="mt-4 border-destructive/40 bg-transparent text-destructive hover:bg-destructive/10"
        >
          {retryText}
        </Button>
      )}
    </Alert>
  )
}
