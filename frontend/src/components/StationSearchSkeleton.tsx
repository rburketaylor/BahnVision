interface StationSearchSkeletonProps {
  count?: number
}

export function StationSearchSkeleton({ count = 3 }: StationSearchSkeletonProps) {
  return (
    <div className="p-1">
      {[...Array(count)].map((_, index) => (
        <div
          key={index}
          className="flex items-center px-4 py-3 animate-pulse"
          role="option"
          aria-disabled="true"
        >
          {/* Icon skeleton */}
          <div className="mr-3 h-8 w-8 rounded-md bg-gray-200" />

          {/* Station info skeleton */}
          <div className="flex-1 min-w-0">
            {/* Station name skeleton */}
            <div className="mb-1 h-4 w-3/4 rounded bg-gray-200" />
            {/* Station place skeleton */}
            <div className="h-3 w-1/2 rounded bg-gray-200" />
          </div>

          {/* Action skeleton */}
          <div className="ml-3 h-6 w-6 rounded bg-gray-200" />
        </div>
      ))}
    </div>
  )
}
