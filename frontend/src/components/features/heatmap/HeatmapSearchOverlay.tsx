/**
 * Heatmap Search Overlay
 * Floating, collapsible station search surface over the map.
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { Search, X } from 'lucide-react'
import { StationSearch } from '../station/StationSearch'
import type { TransitStop } from '../../../types/gtfs'

interface HeatmapSearchOverlayProps {
  onStationSelect?: (stop: TransitStop) => void
  showDetailsLink?: boolean
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        handleClose()
      }

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
      <div className="absolute right-4 top-4 z-[1200]">
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className="btn-bvv inline-flex items-center gap-2 rounded-md border border-border bg-card/96 px-3 py-2 text-small font-semibold text-foreground shadow-surface-2 backdrop-blur hover:border-primary/30 hover:bg-surface-elevated focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label="Search stations (S)"
          title="Search stations (S)"
        >
          <Search className="h-4 w-4" />
          <span>Search</span>
        </button>
      </div>
    )
  }

  return (
    <div
      ref={searchRef}
      className="absolute right-4 top-4 z-[1200] w-[min(24rem,calc(100vw-2rem))]"
    >
      <div className="animate-panel-enter overflow-visible rounded-lg border border-border bg-card/95 shadow-surface-2 backdrop-blur">
        <div className="border-b border-border/70 px-4 pb-2 pt-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <span className="text-h3 text-foreground">Find Station</span>
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="btn-bvv rounded-sm border border-border bg-surface-elevated p-1.5 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
              aria-label="Close search (Escape)"
              title="Close (Escape)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-1 text-tiny text-muted-foreground">
            Press <span className="font-semibold text-foreground">S</span> to toggle search
          </p>
        </div>

        <div className="p-3">
          <StationSearch
            onSelect={handleStationSelect}
            placeholder="Search for a station..."
            autoFocus
          />

          {selectedStop && (
            <div className="animate-content-fade mt-3 rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body font-semibold text-foreground">
                    {selectedStop.name}
                  </p>
                  <p className="mt-1 text-small text-muted-foreground">
                    Station selected. Use the button below for details.
                  </p>
                </div>
                {showDetailsLink && (
                  <button
                    type="button"
                    onClick={handleGoToDetails}
                    className="btn-bvv shrink-0 rounded-md border border-primary/30 bg-primary/15 px-3 py-1.5 text-small font-semibold text-primary hover:bg-primary/24"
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
