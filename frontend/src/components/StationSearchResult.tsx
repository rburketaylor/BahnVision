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
      <span className="font-semibold text-slate-900">{match}</span>
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
      className={`px-3 py-2 cursor-pointer transition-colors ${
        isActive ? 'bg-slate-100' : 'hover:bg-slate-50'
      }`}
    >
      <button
        type="button"
        className={`w-full text-left focus:outline-none ${
          isActive ? 'text-slate-900' : 'text-slate-700'
        }`}
        onMouseDown={event => {
          // Prevent losing focus before click handler fires
          event.preventDefault()
        }}
        onClick={() => onSelect(station)}
      >
        <span className="block text-sm font-medium text-slate-900">
          {highlightMatch(station.name, query)}
        </span>
        <span className="block text-xs text-slate-500">
          {highlightMatch(station.place, query)}
        </span>
      </button>
    </li>
  )
}
