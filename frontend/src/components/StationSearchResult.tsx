/**
 * StationSearchResult
 * Renders an individual station search result within the autocomplete list.
 */

import type { Station } from '../types/api'

interface StationSearchResultProps {
  station: Station
  query: string
  isActive: boolean
  onSelect: (station: Station) => void
  optionId: string
}

function highlightMatch(text: string, query: string) {
  if (!query) {
    return text
  }

  const lowerText = text.toLowerCase()
  const lowerQuery = query.toLowerCase()
  const index = lowerText.indexOf(lowerQuery)

  if (index === -1) {
    return text
  }

  const before = text.slice(0, index)
  const match = text.slice(index, index + query.length)
  const after = text.slice(index + query.length)

  return (
    <>
      {before}
      <span className="font-semibold bg-yellow-200 text-yellow-900 dark:bg-yellow-800 dark:text-yellow-100 px-1 rounded">
        {match}
      </span>
      {after}
    </>
  )
}

export function StationSearchResult({
  station,
  query,
  isActive,
  onSelect,
  optionId,
}: StationSearchResultProps) {
  return (
    <div
      id={optionId}
      role="option"
      aria-selected={isActive}
      className={`px-4 py-3 cursor-pointer transition-colors ${
        isActive ? 'bg-muted' : 'hover:bg-muted'
      }`}
    >
      <button
        type="button"
        className="w-full text-left focus:outline-none"
        onMouseDown={event => {
          // Prevent losing focus before click handler fires
          event.preventDefault()
        }}
        onClick={() => onSelect(station)}
      >
        <div className="font-medium text-foreground">
          {highlightMatch(station.name, query)}
        </div>
        {station.place !== station.name && (
          <div className="text-sm text-gray-500">
            {highlightMatch(station.place, query)}
          </div>
        )}
      </button>
    </div>
  )
}
