/**
 * Station Search
 * Autocomplete component with recent searches and improved UX
 */

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ChangeEvent,
} from 'react'
import DOMPurify from 'dompurify'
import { useStationSearch } from '../../../hooks/useStationSearch'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import type { TransitStop } from '../../../types/gtfs'
import { ApiError } from '../../../services/api'
import {
  getRecentSearches,
  addRecentSearch,
  clearRecentSearches,
  formatRecentSearchTime,
  type RecentSearch,
} from '../../../lib/recentSearches'

// Sanitize user input to prevent XSS
function sanitizeQuery(query: string): string {
  return DOMPurify.sanitize(query, { ALLOWED_TAGS: [] })
}

// Highlighting function - CSS-based approach for security
function highlightMatch(text: string, query: string) {
  if (!query) {
    return { parts: [{ text, isMatch: false }] }
  }

  const lowerText = text.toLowerCase()
  const lowerQuery = query.toLowerCase()
  const index = lowerText.indexOf(lowerQuery)

  if (index === -1) {
    return { parts: [{ text, isMatch: false }] }
  }

  const before = text.slice(0, index)
  const match = text.slice(index, index + query.length)
  const after = text.slice(index + query.length)

  return {
    parts: [
      { text: before, isMatch: false },
      { text: match, isMatch: true },
      { text: after, isMatch: false },
    ].filter(part => part.text.length > 0),
  }
}

// Safe highlighted text component
function HighlightedText({ text, query }: { text: string; query: string }) {
  const { parts } = highlightMatch(text, query)

  return (
    <>
      {parts.map((part, index) => (
        <span
          key={index}
          className={
            part.isMatch
              ? 'font-semibold bg-yellow-200 text-yellow-900 dark:bg-yellow-800 dark:text-yellow-100 px-1 rounded'
              : ''
          }
        >
          {part.text}
        </span>
      ))}
    </>
  )
}

interface StationSearchProps {
  onSelect?: (stop: TransitStop) => void
  initialQuery?: string
  placeholder?: string
  limit?: number
  debounceMs?: number
  label?: string
  showRecentSearches?: boolean
  autoFocus?: boolean
}

const DEFAULT_LIMIT = 40
const DEFAULT_DEBOUNCE = 300

export function StationSearch({
  onSelect,
  initialQuery = '',
  placeholder = 'Search for a station...',
  limit = DEFAULT_LIMIT,
  debounceMs = DEFAULT_DEBOUNCE,
  label = 'Station search',
  showRecentSearches = true,
  autoFocus = false,
}: StationSearchProps) {
  const componentId = useId()
  const inputId = `${componentId}-input`
  const listboxId = `${componentId}-results`

  const [query, setQuery] = useState(initialQuery)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState<number>(-1)
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>(() => getRecentSearches())

  const trimmedQuery = sanitizeQuery(query.trim())
  const debouncedQuery = useDebouncedValue(trimmedQuery, debounceMs)
  const isEnabled = debouncedQuery.length > 0

  const showRecent = showRecentSearches && !isEnabled && recentSearches.length > 0 && isOpen

  const { data, isFetching, isLoading, error, refetch } = useStationSearch(
    { query: debouncedQuery, limit },
    isEnabled
  )

  const results = useMemo(() => data?.data.results ?? [], [data])
  const apiError = error instanceof ApiError ? error : null
  const hasResults = results.length > 0
  const showNoResults =
    isEnabled &&
    !hasResults &&
    !isLoading &&
    !isFetching &&
    (!apiError || apiError.statusCode === 404)
  const showError = Boolean(apiError && apiError.statusCode !== 404)
  const isDropdownVisible =
    isOpen && (showRecent || hasResults || showNoResults || showError || isFetching)
  const isInitialLoading = isLoading || (isFetching && !hasResults)

  // Timeout detection
  const isTimeoutError = apiError?.statusCode === 408
  const hasBeenLoadingTooLong = isFetching && !hasResults && !isLoading

  const containerRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // Calculate all available options
  const allOptions = useMemo(() => {
    if (showRecent) {
      return recentSearches
    } else if (hasResults) {
      return results
    }
    return []
  }, [showRecent, recentSearches, hasResults, results])

  useEffect(() => {
    if (!isEnabled && !showRecent) {
      setIsOpen(false)
      setActiveIndex(-1)
    }
  }, [isEnabled, showRecent])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    if (hasResults || showRecent) {
      setActiveIndex(prev => {
        if (prev >= 0 && prev < allOptions.length) {
          return prev
        }
        return 0
      })
    } else {
      setActiveIndex(-1)
    }
  }, [hasResults, showRecent, allOptions.length, isOpen])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (stop: TransitStop) => {
    setQuery(stop.name)
    setIsOpen(false)
    setActiveIndex(-1)

    // Add to recent searches
    addRecentSearch(stop)
    setRecentSearches(getRecentSearches())

    onSelect?.(stop)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value
    setQuery(value)
    if (!isOpen && (value.trim() || recentSearches.length > 0)) {
      setIsOpen(true)
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownVisible) {
      return
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setActiveIndex(prev => {
          const newIndex = prev + 1
          return newIndex >= allOptions.length ? 0 : newIndex
        })
        break
      case 'ArrowUp':
        event.preventDefault()
        setActiveIndex(prev => {
          const newIndex = prev - 1
          return newIndex < 0 ? allOptions.length - 1 : newIndex
        })
        break
      case 'Enter':
        event.preventDefault()
        if (activeIndex >= 0 && activeIndex < allOptions.length) {
          handleSelect(allOptions[activeIndex])
        }
        break
      case 'Escape':
        setIsOpen(false)
        setActiveIndex(-1)
        inputRef.current?.blur()
        break
    }
  }

  const handleFocus = () => {
    if (query.trim() || recentSearches.length > 0) {
      setIsOpen(true)
    }
  }

  const resetSearchState = () => {
    setQuery('')
    setActiveIndex(-1)
    setIsOpen(false)
  }

  const handleClear = () => {
    resetSearchState()
    inputRef.current?.focus()
  }

  const handleCancelSearch = () => {
    resetSearchState()
  }

  const handleClearRecentSearches = () => {
    clearRecentSearches()
    setRecentSearches([])
    setIsOpen(false)
    setActiveIndex(-1)
  }

  const handleRetry = () => {
    refetch()
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          placeholder={placeholder}
          className="w-full pl-10 pr-12 py-3 text-base border border-border rounded-lg bg-input text-foreground placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-colors"
          autoComplete="off"
          autoCapitalize="off"
          autoFocus={autoFocus}
          spellCheck="false"
          role="combobox"
          aria-label={label}
          aria-expanded={isDropdownVisible}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
          }
        />

        {/* Search icon */}
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg
            className="h-5 w-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        {/* Clear button */}
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Clear search"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Dropdown */}
      {isDropdownVisible && (
        <div
          id={listboxId}
          className="absolute z-50 w-full mt-2 bg-card border border-border rounded-lg shadow-lg max-h-96 overflow-hidden"
          role="listbox"
        >
          {/* Recent searches header */}
          {showRecent && (
            <div className="px-4 py-3 bg-muted border-b border-border flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Recent Searches</span>
              <button
                onClick={handleClearRecentSearches}
                className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                Clear all
              </button>
            </div>
          )}

          {/* Loading state */}
          {isInitialLoading && (
            <div className="px-4 py-8 text-center">
              <div className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border border-gray-300 border-t-primary"></span>
                <span className="text-sm text-gray-500">Searching stations...</span>
              </div>
            </div>
          )}

          {/* Enhanced loading state for long requests */}
          {hasBeenLoadingTooLong && (
            <div className="px-4 py-6 text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <span className="h-4 w-4 animate-spin rounded-full border border-gray-300 border-t-yellow-500"></span>
                <span className="text-sm text-yellow-600">
                  This is taking longer than expected...
                </span>
              </div>
              <button
                onClick={handleCancelSearch}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                Cancel search
              </button>
            </div>
          )}

          {/* Error state */}
          {showError && (
            <div className="px-4 py-6 text-center">
              <div className="text-red-500 text-sm font-medium mb-2">
                {apiError?.message || 'An error occurred'}
              </div>
              <button
                onClick={handleRetry}
                className="text-xs text-primary hover:text-primary/80 underline"
              >
                Try again
              </button>
            </div>
          )}

          {/* Timeout error */}
          {isTimeoutError && (
            <div className="px-4 py-6 text-center">
              <div className="text-yellow-600 text-sm font-medium mb-2">
                Request timed out. The search took too long.
              </div>
              <button
                onClick={handleRetry}
                className="text-xs text-primary hover:text-primary/80 underline mr-4"
              >
                Try again
              </button>
              <button
                onClick={handleCancelSearch}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                Cancel
              </button>
            </div>
          )}

          {/* No results */}
          {showNoResults && (
            <div
              className="px-4 py-6 text-center text-gray-500 text-sm"
              role="option"
              aria-disabled="true"
            >
              No stations found matching "{trimmedQuery}"
            </div>
          )}

          {/* Results */}
          {(hasResults || showRecent) && (
            <ul className="py-2 max-h-80 overflow-y-auto">
              {allOptions.map((station, index) => {
                const isActive = index === activeIndex
                const isRecent = showRecent

                return (
                  <li
                    key={station.id}
                    id={`${listboxId}-option-${index}`}
                    role="option"
                    aria-selected={isActive}
                  >
                    <button
                      className={`
                        w-full px-4 py-3 text-left hover:bg-muted transition-colors
                        ${isActive ? 'bg-muted' : ''}
                        ${isRecent ? 'border-l-2 border-primary bg-primary/5' : ''}
                      `}
                      onClick={() => handleSelect(station)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-foreground truncate">
                            {isRecent ? (
                              station.name
                            ) : (
                              <HighlightedText text={station.name} query={trimmedQuery} />
                            )}
                          </div>
                          {station.id !== station.name && (
                            <div className="text-sm text-gray-500 truncate">ID: {station.id}</div>
                          )}
                        </div>
                        {isRecent && (
                          <span className="text-xs text-gray-400 ml-2 flex-shrink-0">
                            {formatRecentSearchTime((station as RecentSearch).timestamp)}
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}

          {/* Search hint */}
          {isEnabled && !isInitialLoading && hasResults && (
            <div className="px-4 py-2 bg-muted border-t border-border">
              <p className="text-xs text-gray-500">
                Use ↑↓ to navigate, Enter to select, Escape to close
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default StationSearch
