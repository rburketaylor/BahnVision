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
import { Loader2, Search, X } from 'lucide-react'
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
          className={part.isMatch ? 'rounded-sm bg-primary/18 px-1 font-semibold text-primary' : ''}
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
          className="w-full rounded-md border border-input bg-input py-2.5 pl-10 pr-12 text-body text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background transition-[border-color,box-shadow]"
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
          <Search className="h-4 w-4 text-muted-foreground" />
        </div>

        {/* Clear button */}
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {isDropdownVisible && (
        <div
          id={listboxId}
          className="absolute z-50 mt-2 max-h-96 w-full overflow-hidden rounded-md border border-border bg-card shadow-surface-2"
          role="listbox"
        >
          {/* Recent searches header */}
          {showRecent && (
            <div className="px-4 py-3 bg-muted border-b border-border flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Recent Searches</span>
              <button
                onClick={handleClearRecentSearches}
                className="text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                Clear all
              </button>
            </div>
          )}

          {/* Loading state */}
          {isInitialLoading && (
            <div className="px-4 py-8 text-center">
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Searching stations...</span>
              </div>
            </div>
          )}

          {/* Enhanced loading state for long requests */}
          {hasBeenLoadingTooLong && (
            <div className="px-4 py-6 text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <Loader2 className="h-4 w-4 animate-spin text-status-warning" />
                <span className="text-sm text-status-warning">
                  This is taking longer than expected...
                </span>
              </div>
              <button
                onClick={handleCancelSearch}
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                Cancel search
              </button>
            </div>
          )}

          {/* Error state */}
          {showError && (
            <div className="px-4 py-6 text-center">
              <div className="mb-2 text-sm font-medium text-status-critical">
                {apiError?.message || 'An error occurred'}
              </div>
              <button
                onClick={handleRetry}
                className="text-xs text-primary underline hover:text-primary/80"
              >
                Try again
              </button>
            </div>
          )}

          {/* Timeout error */}
          {isTimeoutError && (
            <div className="px-4 py-6 text-center">
              <div className="mb-2 text-sm font-medium text-status-warning">
                Request timed out. The search took too long.
              </div>
              <button
                onClick={handleRetry}
                className="mr-4 text-xs text-primary underline hover:text-primary/80"
              >
                Try again
              </button>
              <button
                onClick={handleCancelSearch}
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          )}

          {/* No results */}
          {showNoResults && (
            <div
              className="px-4 py-6 text-center text-sm text-muted-foreground"
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
                        w-full px-4 py-3 text-left transition-colors hover:bg-surface-elevated
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
                            <div className="truncate text-sm text-muted-foreground">
                              ID: {station.id}
                            </div>
                          )}
                        </div>
                        {isRecent && (
                          <span className="ml-2 flex-shrink-0 text-xs text-muted-foreground/80">
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
              <p className="text-xs text-muted-foreground">
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
