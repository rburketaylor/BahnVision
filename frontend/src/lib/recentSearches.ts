/**
 * Recent Searches Management
 * Handles storing and retrieving recent station searches from localStorage
 */

import type { Station } from '../types/api'

const RECENT_SEARCHES_KEY = 'bahnvision-recent-searches'
const MAX_RECENT_SEARCHES = 8

export interface RecentSearch extends Station {
  timestamp: number
}

export function getRecentSearches(): RecentSearch[] {
  if (typeof window === 'undefined') return []

  try {
    const stored = localStorage.getItem(RECENT_SEARCHES_KEY)
    if (!stored) return []

    const searches = JSON.parse(stored) as RecentSearch[]
    return searches.sort((a, b) => b.timestamp - a.timestamp).slice(0, MAX_RECENT_SEARCHES)
  } catch {
    return []
  }
}

export function addRecentSearch(station: Station): void {
  if (typeof window === 'undefined') return

  try {
    const searches = getRecentSearches()

    // Remove existing entry with same ID if it exists
    const filteredSearches = searches.filter(search => search.id !== station.id)

    // Add new entry at the beginning
    const newSearch: RecentSearch = {
      ...station,
      timestamp: Date.now(),
    }

    const updatedSearches = [newSearch, ...filteredSearches].slice(0, MAX_RECENT_SEARCHES)
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updatedSearches))
  } catch {
    // Silently fail if localStorage is not available
  }
}

export function clearRecentSearches(): void {
  if (typeof window === 'undefined') return

  try {
    localStorage.removeItem(RECENT_SEARCHES_KEY)
  } catch {
    // Silently fail if localStorage is not available
  }
}

export function formatRecentSearchTime(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp

  if (diff < 60 * 1000) {
    return 'Just now'
  } else if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes}m ago`
  } else if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours}h ago`
  } else {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    return `${days}d ago`
  }
}
