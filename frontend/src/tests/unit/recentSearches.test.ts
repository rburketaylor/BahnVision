/**
 * Tests for recentSearches utility functions
 * Target: lib/recentSearches.ts (10.9% mutation score → 80%+)
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
    getRecentSearches,
    addRecentSearch,
    clearRecentSearches,
    formatRecentSearchTime,
    type RecentSearch,
} from '../../lib/recentSearches'
import type { TransitStop } from '../../types/gtfs'

const RECENT_SEARCHES_KEY = 'bahnvision-recent-searches'
const MAX_RECENT_SEARCHES = 8

// Mock localStorage
const localStorageMock = (() => {
    let store: Record<string, string> = {}
    return {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => {
            store[key] = value
        }),
        removeItem: vi.fn((key: string) => {
            delete store[key]
        }),
        clear: vi.fn(() => {
            store = {}
        }),
        get length() {
            return Object.keys(store).length
        },
        key: vi.fn((index: number) => Object.keys(store)[index] || null),
    }
})()

Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
})

// Mock Date.now for consistent testing
const NOW = 1704067200000 // 2024-01-01 00:00:00 UTC

// Helper to create a complete mock stop
function createMockStop(overrides: Partial<TransitStop> & { id: string; name: string }): TransitStop {
    return {
        latitude: 48.137,
        longitude: 11.575,
        zone_id: null,
        wheelchair_boarding: 0,
        ...overrides,
    }
}

// Helper to create a complete mock recent search
function createMockRecentSearch(
    overrides: Partial<RecentSearch> & { id: string; name: string; timestamp: number }
): RecentSearch {
    return {
        latitude: 48.137,
        longitude: 11.575,
        zone_id: null,
        wheelchair_boarding: 0,
        ...overrides,
    }
}

describe('recentSearches', () => {
    beforeEach(() => {
        localStorageMock.clear()
        vi.clearAllMocks()
        vi.spyOn(Date, 'now').mockReturnValue(NOW)
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getRecentSearches', () => {
        it('returns empty array when nothing stored', () => {
            const result = getRecentSearches()
            expect(result).toEqual([])
            expect(localStorageMock.getItem).toHaveBeenCalledWith(RECENT_SEARCHES_KEY)
        })

        it('returns empty array when localStorage value is null', () => {
            localStorageMock.getItem.mockReturnValueOnce(null)
            const result = getRecentSearches()
            expect(result).toEqual([])
        })

        it('parses and returns stored searches', () => {
            const searches: RecentSearch[] = [
                createMockRecentSearch({
                    id: 'stop1',
                    name: 'Marienplatz',
                    timestamp: NOW - 1000,
                }),
            ]
            localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(searches))

            const result = getRecentSearches()
            expect(result).toHaveLength(1)
            expect(result[0].name).toBe('Marienplatz')
        })

        it('sorts searches by timestamp descending (newest first)', () => {
            const searches: RecentSearch[] = [
                createMockRecentSearch({ id: 'old', name: 'Old', timestamp: NOW - 10000 }),
                createMockRecentSearch({ id: 'new', name: 'New', timestamp: NOW - 1000 }),
                createMockRecentSearch({ id: 'mid', name: 'Mid', timestamp: NOW - 5000 }),
            ]
            localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(searches))

            const result = getRecentSearches()
            expect(result[0].name).toBe('New')
            expect(result[1].name).toBe('Mid')
            expect(result[2].name).toBe('Old')
        })

        it('limits results to MAX_RECENT_SEARCHES', () => {
            const searches: RecentSearch[] = Array.from({ length: 15 }, (_, i) =>
                createMockRecentSearch({
                    id: `stop${i}`,
                    name: `Stop ${i}`,
                    timestamp: NOW - i * 1000,
                })
            )
            localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(searches))

            const result = getRecentSearches()
            expect(result).toHaveLength(MAX_RECENT_SEARCHES)
        })

        it('returns empty array on parse error', () => {
            localStorageMock.getItem.mockReturnValueOnce('invalid json {{{')
            const result = getRecentSearches()
            expect(result).toEqual([])
        })
    })

    describe('addRecentSearch', () => {
        const mockStop: TransitStop = createMockStop({
            id: 'stop1',
            name: 'Marienplatz',
        })

        it('adds new search to localStorage', () => {
            addRecentSearch(mockStop)

            expect(localStorageMock.setItem).toHaveBeenCalledWith(
                RECENT_SEARCHES_KEY,
                expect.any(String)
            )

            const storedValue = localStorageMock.setItem.mock.calls[0][1]
            const parsed = JSON.parse(storedValue)
            expect(parsed).toHaveLength(1)
            expect(parsed[0].id).toBe('stop1')
            expect(parsed[0].name).toBe('Marienplatz')
            expect(parsed[0].timestamp).toBe(NOW)
        })

        it('deduplicates by ID (removes existing, adds new at front)', () => {
            const existingSearches: RecentSearch[] = [
                createMockRecentSearch({ id: 'stop1', name: 'Marienplatz', timestamp: NOW - 5000 }),
                createMockRecentSearch({ id: 'stop2', name: 'Hauptbahnhof', timestamp: NOW - 10000 }),
            ]
            localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches))

            addRecentSearch(mockStop)

            const storedValue = localStorageMock.setItem.mock.calls[0][1]
            const parsed = JSON.parse(storedValue)
            expect(parsed).toHaveLength(2)
            expect(parsed[0].id).toBe('stop1') // New entry at front
            expect(parsed[0].timestamp).toBe(NOW) // Updated timestamp
            expect(parsed[1].id).toBe('stop2')
        })

        it('limits to MAX_RECENT_SEARCHES entries', () => {
            const existingSearches: RecentSearch[] = Array.from({ length: 10 }, (_, i) =>
                createMockRecentSearch({
                    id: `stop${i}`,
                    name: `Stop ${i}`,
                    timestamp: NOW - i * 1000,
                })
            )
            localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches))

            const newStop: TransitStop = createMockStop({
                id: 'newstop',
                name: 'New Station',
            })
            addRecentSearch(newStop)

            const storedValue = localStorageMock.setItem.mock.calls[0][1]
            const parsed = JSON.parse(storedValue)
            expect(parsed).toHaveLength(MAX_RECENT_SEARCHES)
            expect(parsed[0].id).toBe('newstop') // New entry at front
        })

        it('handles localStorage errors silently', () => {
            localStorageMock.setItem.mockImplementationOnce(() => {
                throw new Error('QuotaExceededError')
            })

            // Should not throw
            expect(() => addRecentSearch(mockStop)).not.toThrow()
        })
    })

    describe('clearRecentSearches', () => {
        it('removes searches from localStorage', () => {
            clearRecentSearches()
            expect(localStorageMock.removeItem).toHaveBeenCalledWith(RECENT_SEARCHES_KEY)
        })

        it('handles localStorage errors silently', () => {
            localStorageMock.removeItem.mockImplementationOnce(() => {
                throw new Error('SecurityError')
            })

            // Should not throw
            expect(() => clearRecentSearches()).not.toThrow()
        })
    })

    describe('formatRecentSearchTime', () => {
        it('returns "Just now" for timestamps less than 1 minute ago', () => {
            expect(formatRecentSearchTime(NOW - 30 * 1000)).toBe('Just now') // 30 seconds ago
            expect(formatRecentSearchTime(NOW - 59 * 1000)).toBe('Just now') // 59 seconds ago
            expect(formatRecentSearchTime(NOW)).toBe('Just now') // 0 seconds ago
        })

        it('returns "Xm ago" for timestamps 1-59 minutes ago', () => {
            expect(formatRecentSearchTime(NOW - 60 * 1000)).toBe('1m ago') // 1 minute
            expect(formatRecentSearchTime(NOW - 5 * 60 * 1000)).toBe('5m ago') // 5 minutes
            expect(formatRecentSearchTime(NOW - 30 * 60 * 1000)).toBe('30m ago') // 30 minutes
            expect(formatRecentSearchTime(NOW - 59 * 60 * 1000)).toBe('59m ago') // 59 minutes
        })

        it('returns "Xh ago" for timestamps 1-23 hours ago', () => {
            expect(formatRecentSearchTime(NOW - 60 * 60 * 1000)).toBe('1h ago') // 1 hour
            expect(formatRecentSearchTime(NOW - 5 * 60 * 60 * 1000)).toBe('5h ago') // 5 hours
            expect(formatRecentSearchTime(NOW - 12 * 60 * 60 * 1000)).toBe('12h ago') // 12 hours
            expect(formatRecentSearchTime(NOW - 23 * 60 * 60 * 1000)).toBe('23h ago') // 23 hours
        })

        it('returns "Xd ago" for timestamps 1+ days ago', () => {
            expect(formatRecentSearchTime(NOW - 24 * 60 * 60 * 1000)).toBe('1d ago') // 1 day
            expect(formatRecentSearchTime(NOW - 3 * 24 * 60 * 60 * 1000)).toBe('3d ago') // 3 days
            expect(formatRecentSearchTime(NOW - 7 * 24 * 60 * 60 * 1000)).toBe('7d ago') // 7 days
            expect(formatRecentSearchTime(NOW - 30 * 24 * 60 * 60 * 1000)).toBe('30d ago') // 30 days
        })

        it('handles edge case at exact minute boundary', () => {
            // At exactly 60 seconds, should show "1m ago" not "Just now"
            expect(formatRecentSearchTime(NOW - 60 * 1000)).toBe('1m ago')
        })

        it('handles edge case at exact hour boundary', () => {
            // At exactly 60 minutes, should show "1h ago" not "60m ago"
            expect(formatRecentSearchTime(NOW - 60 * 60 * 1000)).toBe('1h ago')
        })

        it('handles edge case at exact day boundary', () => {
            // At exactly 24 hours, should show "1d ago" not "24h ago"
            expect(formatRecentSearchTime(NOW - 24 * 60 * 60 * 1000)).toBe('1d ago')
        })
    })
})
