/**
 * StationSearch
 * Accessible autocomplete component for MVG stations.
 */

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ChangeEvent } from 'react'
import { useStationSearch } from '../hooks/useStationSearch'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import type { Station } from '../types/api'
import { ApiError } from '../services/api'
import { StationSearchResult } from './StationSearchResult'
import { StationSearchLoading } from './StationSearchLoading'

interface StationSearchProps {
  onSelect?: (station: Station) => void
  initialQuery?: string
  placeholder?: string
  limit?: number
  debounceMs?: number
  label?: string
}

const DEFAULT_LIMIT = 8
const DEFAULT_DEBOUNCE = 300

export function StationSearch({
  onSelect,
  initialQuery = '',
  placeholder = 'Search for a station',
  limit = DEFAULT_LIMIT,
  debounceMs = DEFAULT_DEBOUNCE,
  label = 'Station search',
}: StationSearchProps) {
  const componentId = useId()
  const inputId = `${componentId}-input`
  const listboxId = `${componentId}-results`

  const [query, setQuery] = useState(initialQuery)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState<number>(-1)

  const trimmedQuery = query.trim()
  const debouncedQuery = useDebouncedValue(trimmedQuery, debounceMs)
  const isEnabled = debouncedQuery.length > 0

  const {
    data,
    isFetching,
    isLoading,
    error,
    refetch,
  } = useStationSearch({ query: debouncedQuery, limit }, isEnabled)

  const results = useMemo(() => data?.data.results ?? [], [data])
  const apiError = error instanceof ApiError ? error : null
  const hasResults = results.length > 0
  const showNoResults =
    isEnabled && !hasResults && !isLoading && !isFetching && (!apiError || apiError.statusCode === 404)
  const showError = Boolean(apiError && apiError.statusCode !== 404)
  const isDropdownVisible = isOpen && (hasResults || showNoResults || showError || isFetching)
  const isInitialLoading = isLoading || (isFetching && !hasResults)

  // Enhanced timeout detection
  const isTimeoutError = apiError?.statusCode === 408
  const hasBeenLoadingTooLong = isFetching && !hasResults && !isLoading

  // Enhanced loading state detection
  const showEnhancedLoading = isInitialLoading && isEnabled && debouncedQuery.length > 0

  const containerRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!isEnabled) {
      setIsOpen(false)
      setActiveIndex(-1)
    }
  }, [isEnabled])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    if (hasResults) {
      setActiveIndex(prev => {
        if (prev >= 0 && prev < results.length) {
          return prev
        }
        return 0
      })
    } else {
      setActiveIndex(-1)
    }
  }, [hasResults, results.length, isOpen])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectStation = (station: Station) => {
    setQuery(station.name)
    setIsOpen(false)
    setActiveIndex(-1)
    onSelect?.(station)
  }

  const cancelSearch = () => {
    setQuery('')
    setIsOpen(false)
    setActiveIndex(-1)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownVisible || (!hasResults && !showNoResults && !showError)) {
      return
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!hasResults) return
      setIsOpen(true)
      setActiveIndex(prev => {
        const nextIndex = prev + 1
        return nextIndex >= results.length ? 0 : nextIndex
      })
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      if (!hasResults) return
      setIsOpen(true)
      setActiveIndex(prev => {
        const nextIndex = prev - 1
        return nextIndex < 0 ? results.length - 1 : nextIndex
      })
    } else if (event.key === 'Enter') {
      if (hasResults) {
        event.preventDefault()
        const station = activeIndex >= 0 ? results[activeIndex] : results[0]
        if (station) {
          selectStation(station)
        }
      }
    } else if (event.key === 'Escape') {
      setIsOpen(false)
      setActiveIndex(-1)
      inputRef.current?.blur()
    }
  }

  const handleInputFocus = () => {
    if (isEnabled) {
      setIsOpen(true)
    }
  }

  // Cancel ongoing search when user clears the input
  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextValue = event.target.value
    setQuery(nextValue)

    // If clearing the input, close dropdown immediately and cancel any ongoing requests
    if (nextValue.trim().length === 0) {
      setIsOpen(false)
      setActiveIndex(-1)
    } else {
      setIsOpen(true)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-gray-700">
        {label}
      </label>
      <div className="relative">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          role="combobox"
          aria-expanded={isDropdownVisible}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={
            isDropdownVisible && hasResults && activeIndex >= 0
              ? `${listboxId}-option-${results[activeIndex].id}`
              : undefined
          }
          className={`w-full rounded-lg border px-4 py-3 text-base shadow-sm focus:outline-none focus:ring-2 transition-all ${
              showEnhancedLoading
                ? 'border-blue-300 bg-blue-50 text-gray-900 focus:border-blue-500 focus:ring-blue-500/20'
                : 'border-gray-300 bg-white text-gray-900 focus:border-primary focus:ring-primary/40'
            }`}
        />
        {showEnhancedLoading && (
          <div className="absolute inset-y-0 right-3 flex items-center">
            <div className="flex items-center gap-2 pr-2">
              <span className="text-xs text-blue-600 font-medium animate-pulse">
                Searching...
              </span>
              <div className={`h-5 w-5 animate-spin rounded-full border-2 ${
                hasBeenLoadingTooLong
                  ? 'border-orange-300 border-t-orange-600'
                  : 'border-blue-300 border-t-blue-600'
              }`} />
            </div>
          </div>
        )}
      </div>
      <div aria-live="polite" className="sr-only">
        {isLoading && 'Loading stations'}
        {showNoResults && 'No stations found'}
        {showError && 'Unable to load stations'}
      </div>
      {isDropdownVisible && (
        <div
          id={listboxId}
          role="listbox"
          className="absolute z-40 mt-2 max-h-96 w-full overflow-auto rounded-lg border border-gray-200 bg-white text-gray-900 shadow-lg"
        >
          {/* Enhanced loading state */}
          {showEnhancedLoading && (
            <StationSearchLoading
              query={debouncedQuery}
              hasBeenLoadingTooLong={hasBeenLoadingTooLong}
              onCancel={cancelSearch}
            />
          )}

          {/* Regular results */}
          {!showEnhancedLoading && hasResults &&
            results.map((station, index) => (
              <StationSearchResult
                key={station.id}
                station={station}
                query={debouncedQuery}
                isActive={index === activeIndex}
                onSelect={selectStation}
                optionId={`${listboxId}-option-${station.id}`}
              />
            ))}

          {/* No results state */}
          {!showEnhancedLoading && showNoResults && (
            <div className="px-4 py-3 text-sm text-gray-400" role="option" aria-disabled="true">
              No stations found for "{debouncedQuery}"
            </div>
          )}

          {/* Error state */}
          {!showEnhancedLoading && showError && (
            <div className="px-4 py-3 text-sm text-red-500" role="option" aria-disabled="true">
              {isTimeoutError ? (
                <>
                  <div className="mb-2">
                    <strong>Search timed out.</strong> The station search is taking longer than expected.
                  </div>
                  <div className="mb-2 p-2 bg-yellow-50 rounded border border-yellow-200 text-xs">
                    <strong>This sometimes happens on first searches</strong> when the backend is loading data from external services. Please try again.
                  </div>
                  <button
                    type="button"
                    className="font-medium text-red-400 underline underline-offset-2 hover:text-red-300"
                    onClick={() => refetch()}
                  >
                    Try again
                  </button>
                </>
              ) : (
                <>
                  <div className="mb-2">
                    <strong>Unable to load stations.</strong> Please check your connection and try again.
                  </div>
                  <button
                    type="button"
                    className="font-medium text-red-400 underline underline-offset-2 hover:text-red-300"
                    onClick={() => refetch()}
                  >
                    Try again
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default StationSearch
