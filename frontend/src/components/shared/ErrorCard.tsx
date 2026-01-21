/**
 * ErrorCard
 * A standardized error display component with optional retry action
 */

interface ErrorCardProps {
  title: string
  message: string
  onRetry?: () => void
  retryText?: string
}

export function ErrorCard({ title, message, onRetry, retryText = 'Retry' }: ErrorCardProps) {
  return (
    <div className="bg-red-50 border border-red-200 text-red-800 p-6 rounded-lg dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
      <div className="flex items-center gap-3">
        <span className="text-2xl">🚨</span>
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-sm mt-1">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-red-100 text-red-800 rounded-lg hover:bg-red-200 transition-colors dark:bg-red-800 dark:text-red-100 dark:hover:bg-red-700"
        >
          {retryText}
        </button>
      )}
    </div>
  )
}
