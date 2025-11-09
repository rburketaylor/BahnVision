import { StationSearchSkeleton } from './StationSearchSkeleton'

interface StationSearchLoadingProps {
  query: string
  hasBeenLoadingTooLong: boolean
  onCancel: () => void
}

export function StationSearchLoading({ query, hasBeenLoadingTooLong, onCancel }: StationSearchLoadingProps) {
  return (
    <div className="p-4">
      {/* Loading header with context */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <div className={`h-5 w-5 animate-spin rounded-full border-2 ${
              hasBeenLoadingTooLong
                ? 'border-orange-300 border-t-orange-600'
                : 'border-blue-300 border-t-blue-600'
            }`} />
            <span className={`text-sm font-medium ${
              hasBeenLoadingTooLong ? 'text-orange-600' : 'text-blue-600'
            }`}>
              {hasBeenLoadingTooLong ? 'Still searching...' : 'Searching stations'}
            </span>
          </div>
          <span className="text-xs text-gray-500">
            for "{query.length > 20 ? `${query.slice(0, 20)}...` : query}"
          </span>
        </div>

        {hasBeenLoadingTooLong && (
          <button
            type="button"
            onClick={onCancel}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Loading message with tips */}
      <div className="mb-3 p-2 bg-blue-50 rounded border border-blue-200">
        {hasBeenLoadingTooLong ? (
          <>
            <p className="text-xs text-blue-700">
              <strong>Taking longer than expected.</strong> This might be due to:
            </p>
            <ul className="mt-1 ml-4 list-disc list-inside text-xs text-blue-700">
              <li>Slow network connection</li>
              <li>Server processing delay</li>
              <li>Large number of results</li>
              <li>First search (backend warming up caches)</li>
            </ul>
            <div className="mt-2 p-2 bg-yellow-50 rounded border border-yellow-200">
              <strong>Tip:</strong> First searches sometimes take longer as the system loads data. Subsequent searches will be much faster.
            </div>
          </>
        ) : (
          <p className="text-xs text-blue-700">
            <strong>Finding stations...</strong> This usually takes just a moment.
            {query.length === 1 && (
              <>
                {" "}
                <em>Single character searches may return more results and take slightly longer.</em>
              </>
            )}
          </p>
        )}
      </div>

      {/* Skeleton results */}
      <StationSearchSkeleton count={3} />
    </div>
  )
}