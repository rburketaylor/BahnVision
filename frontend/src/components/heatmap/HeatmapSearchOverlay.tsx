/**
 * Heatmap Search Overlay
 * Floating, collapsible search bar that sits at the top of the heatmap.
 * When a station is selected, it calls onStationSelect to zoom/highlight.
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { StationSearch } from '../StationSearch'
import type { TransitStop } from '../../types/gtfs'

interface HeatmapSearchOverlayProps {
  /** Callback when station is selected (zooms map to station) */
  onStationSelect?: (stop: TransitStop) => void
  /** Whether to show a "Go to details" button after selection */
  showDetailsLink?: boolean
}

function SearchIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

export function HeatmapSearchOverlay({
  onStationSelect,
  showDetailsLink = true,
}: HeatmapSearchOverlayProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [selectedStop, setSelectedStop] = useState<TransitStop | null>(null)
  const searchRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const handleStationSelect = (stop: TransitStop) => {
    setSelectedStop(stop)
    onStationSelect?.(stop)
    // Keep search expanded to show the selected station info
  }

  const handleGoToDetails = () => {
    if (selectedStop) {
      navigate(`/station/${selectedStop.id}`)
    }
  }

  const handleClose = () => {
    setIsExpanded(false)
    setSelectedStop(null)
  }

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        handleClose()
      }
      // Toggle with 'S' key when not typing
      if (e.key === 's' || e.key === 'S') {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
        e.preventDefault()
        setIsExpanded(prev => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isExpanded])

  if (!isExpanded) {
    return (
      <div className="absolute top-4 right-4 z-[1200]">
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card/95 border border-border text-foreground shadow-lg backdrop-blur hover:bg-muted transition-colors"
          aria-label="Search stations (S)"
          title="Search stations (S)"
        >
          <SearchIcon />
          <span className="text-xs font-medium">Search</span>
        </button>
      </div>
    )
  }

  return (
    <div
      ref={searchRef}
      className="absolute top-4 right-4 z-[1200] w-[min(22rem,calc(100vw-2rem))]"
    >
      <div className="bg-card/95 border border-border shadow-xl backdrop-blur rounded-xl overflow-visible">
        <div className="px-4 pt-3 pb-2 border-b border-border/60">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <SearchIcon />
              <span className="text-sm font-medium text-foreground">Find Station</span>
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="p-1.5 rounded-md hover:bg-muted transition-colors"
              aria-label="Close search (Escape)"
              title="Close (Escape)"
            >
              <CloseIcon />
            </button>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Press <span className="font-medium text-foreground">S</span> to toggle search
          </p>
        </div>

        <div className="p-3">
          <StationSearch
            onSelect={handleStationSelect}
            placeholder="Search for a station..."
            autoFocus
          />

          {selectedStop && (
            <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border/60">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {selectedStop.name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Click on map or use button below
                  </p>
                </div>
                {showDetailsLink && (
                  <button
                    type="button"
                    onClick={handleGoToDetails}
                    className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
                  >
                    View Details
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
