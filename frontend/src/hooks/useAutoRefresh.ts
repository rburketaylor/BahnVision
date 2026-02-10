/**
 * useAutoRefresh
 * A hook for managing auto-refresh functionality with configurable interval
 */

import { useEffect, useRef } from 'react'

interface UseAutoRefreshOptions {
  callback: () => void
  enabled?: boolean
  intervalMs?: number
  runOnMount?: boolean
}

export function useAutoRefresh({
  callback,
  enabled = true,
  intervalMs = 30000,
  runOnMount = true,
}: UseAutoRefreshOptions) {
  const callbackRef = useRef(callback)

  // Update ref callback in a separate effect to avoid updating during render
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return

    // Run immediately on mount if requested
    if (runOnMount) {
      callbackRef.current()
    }

    const interval = window.setInterval(() => {
      callbackRef.current()
    }, intervalMs)

    return () => {
      if (interval) window.clearInterval(interval)
    }
  }, [enabled, intervalMs, runOnMount])
}
