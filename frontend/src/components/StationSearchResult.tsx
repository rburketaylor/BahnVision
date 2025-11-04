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
      <span className="font-semibold text-gray-900">{match}</span>
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
    <li
      id={optionId}
      role="option"
      aria-selected={isActive}
      className={`cursor-pointer border-b border-gray-200 px-4 py-3 transition-colors last:border-b-0 ${
        isActive ? 'bg-gray-100' : 'hover:bg-gray-100'
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
        <span className="block text-base font-medium text-gray-900">
          {highlightMatch(station.name, query)}
        </span>
        <span className="block text-sm text-gray-600">
          {highlightMatch(station.place, query)}
        </span>
      </button>
    </li>
  )
}
