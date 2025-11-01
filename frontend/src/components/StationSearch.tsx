/**
 * StationSearch
 * Accessible autocomplete component for MVG stations.
 */

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useStationSearch } from '../hooks/useStationSearch'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import type { Station } from '../types/api'
import { ApiError } from '../services/api'
import { StationSearchResult } from './StationSearchResult'

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
  } = useStationSearch({ q: debouncedQuery, limit }, isEnabled)

  const results = useMemo(() => data?.data.results ?? [], [data])
  const apiError = error instanceof ApiError ? error : null
  const hasResults = results.length > 0
  const showNoResults =
    isEnabled && !hasResults && !isLoading && !isFetching && (!apiError || apiError.statusCode === 404)
  const showError = Boolean(apiError && apiError.statusCode !== 404)
  const isDropdownVisible = isOpen && (hasResults || showNoResults || showError || isFetching)
  const isInitialLoading = isLoading || (isFetching && !hasResults)

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

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 mb-1">
        {label}
      </label>
      <div className="relative">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          value={query}
          onChange={event => {
            const nextValue = event.target.value
            setQuery(nextValue)
            setIsOpen(nextValue.trim().length > 0)
          }}
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
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
        />
        {isInitialLoading && (
          <div className="absolute inset-y-0 right-3 flex items-center">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-500" />
          </div>
        )}
      </div>
      <div aria-live="polite" className="sr-only">
        {isLoading && 'Loading stations'}
        {showNoResults && 'No stations found'}
        {showError && 'Unable to load stations'}
      </div>
      {isDropdownVisible && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-2 max-h-72 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          {hasResults &&
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

          {showNoResults && (
            <li className="px-3 py-2 text-sm text-slate-500" role="option" aria-disabled="true">
              No stations found
            </li>
          )}

          {showError && (
            <li className="px-3 py-2 text-sm text-red-600" role="option" aria-disabled="true">
              Unable to load stations.{' '}
              <button
                type="button"
                className="font-medium text-red-700 underline underline-offset-2 hover:text-red-800"
                onClick={() => refetch()}
              >
                Try again
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

export default StationSearch
