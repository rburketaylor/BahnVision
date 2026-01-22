/**
 * Heatmap Overlay Panel
 * Floating, toggleable panel that sits above the map.
 * BVV-styled with blue accent strip and stronger backdrop blur.
 */

import { useEffect, useId, useRef, type ReactNode } from 'react'

interface HeatmapOverlayPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  hasError?: boolean
  isLoading?: boolean
  onRefresh: () => void
  children: ReactNode
}

function ControlsIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 6h16M7 12h10M10 18h4"
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

export function HeatmapOverlayPanel({
  open,
  onOpenChange,
  title,
  description,
  hasError = false,
  isLoading = false,
  onRefresh,
  children,
}: HeatmapOverlayPanelProps) {
  const panelId = useId()
  const showButtonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!open) {
      showButtonRef.current?.focus()
    }
  }, [open])

  if (!open) {
    return (
      <div className="absolute top-4 left-4 z-[1200]">
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          ref={showButtonRef}
          className="btn-bvv flex items-center gap-2 px-3 py-2 rounded-lg bg-card/95 border border-border text-foreground shadow-lg backdrop-blur-md hover:bg-muted transition-colors"
          aria-label="Show heatmap controls (C)"
          aria-expanded={false}
          title="Show controls (C)"
        >
          <ControlsIcon />
          <span className="text-small font-medium">Controls</span>
          {hasError && (
            <span
              className="w-2 h-2 rounded-full bg-status-critical animate-pulse"
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    )
  }

  return (
    <aside
      className="absolute top-4 bottom-4 left-4 z-[1200] w-[min(26rem,calc(100vw-2rem))]"
      aria-label="Heatmap controls"
    >
      <div
        id={panelId}
        className="bg-card/95 border border-border shadow-xl backdrop-blur-md rounded-xl h-full max-h-full flex flex-col overflow-hidden animate-slideIn"
        style={{
          animationDuration: '300ms',
          animationTimingFunction: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        }}
      >
        {/* Blue accent strip at top */}
        <div className="h-1 bg-primary shrink-0" />

        <div className="px-4 pt-4 pb-3 border-b border-border/60">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-h1 text-foreground truncate">{title}</h1>
              <p className="text-small text-muted mt-1">{description}</p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={onRefresh}
                disabled={isLoading}
                className="btn-bvv flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                aria-label="Refresh heatmap data"
                title="Refresh"
              >
                <svg
                  className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                <span className="text-small font-medium hidden sm:inline">
                  {isLoading ? 'Loading' : 'Refresh'}
                </span>
              </button>

              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="btn-bvv p-2 rounded-lg border border-border bg-card hover:bg-muted transition-colors"
                aria-label="Hide heatmap controls (C)"
                aria-expanded={true}
                title="Hide controls (C)"
              >
                <CloseIcon />
              </button>
            </div>
          </div>
          <p className="text-tiny text-muted mt-2">
            Tip: press <span className="font-medium text-foreground">C</span> to toggle controls.
          </p>
        </div>

        <div className="p-4 overflow-auto space-y-3">{children}</div>
      </div>
    </aside>
  )
}
