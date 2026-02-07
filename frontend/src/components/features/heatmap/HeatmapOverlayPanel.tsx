/**
 * Heatmap Overlay Panel
 * Floating, toggleable control panel over the map.
 */

import { useEffect, useId, useRef, type ReactNode } from 'react'
import { PanelLeftClose, RefreshCw, SlidersHorizontal, X } from 'lucide-react'

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
      <div className="absolute left-4 top-4 z-[1200]">
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          ref={showButtonRef}
          className="btn-bvv inline-flex items-center gap-2 rounded-md border border-border bg-card/96 px-3 py-2 text-small font-semibold text-foreground shadow-surface-2 backdrop-blur hover:border-primary/30 hover:bg-surface-elevated"
          aria-label="Show heatmap controls (C)"
          aria-expanded={false}
          title="Show controls (C)"
        >
          <SlidersHorizontal className="h-4 w-4" />
          <span>Controls</span>
          {hasError && (
            <span
              className="h-2 w-2 rounded-full bg-status-critical animate-status-pulse"
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    )
  }

  return (
    <aside
      className="absolute bottom-4 left-4 top-4 z-[1200] w-[min(26rem,calc(100vw-2rem))]"
      aria-label="Heatmap controls"
    >
      <div
        id={panelId}
        className="animate-panel-enter flex h-full max-h-full flex-col overflow-hidden rounded-lg border border-border/90 shadow-surface-2"
        style={{
          backgroundColor: 'hsl(var(--surface-elevated) / 0.94)',
          backdropFilter: 'blur(14px) saturate(125%)',
          WebkitBackdropFilter: 'blur(14px) saturate(125%)',
        }}
      >
        <div className="h-1.5 shrink-0 bg-primary" />

        <div className="border-b border-border/70 px-4 pb-3 pt-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-h1 text-foreground truncate">{title}</h1>
              <p className="mt-1 text-small text-muted-foreground">{description}</p>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={onRefresh}
                disabled={isLoading}
                className="btn-bvv inline-flex items-center gap-2 rounded-md border border-primary/30 bg-primary/12 px-3 py-2 text-small font-semibold text-primary hover:bg-primary/18 disabled:opacity-50"
                aria-label="Refresh heatmap data"
                title="Refresh"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">{isLoading ? 'Loading' : 'Refresh'}</span>
              </button>

              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="btn-bvv rounded-md border border-border bg-surface-elevated p-2 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
                aria-label="Hide heatmap controls (C)"
                aria-expanded={true}
                title="Hide controls (C)"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
          <p className="mt-2 text-tiny text-muted-foreground">
            Tip: press <span className="font-semibold text-foreground">C</span> to toggle controls.
          </p>
        </div>

        <div className="space-y-3 overflow-auto p-4">{children}</div>

        <div className="border-t border-border/70 px-4 py-2 text-tiny text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <PanelLeftClose className="h-3.5 w-3.5" />
            Panel mode
          </span>
        </div>
      </div>
    </aside>
  )
}
