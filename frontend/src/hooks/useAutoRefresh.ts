/**
 * useAutoRefresh
 * A hook for managing auto-refresh functionality with configurable interval
 */

import { useCallback, useEffect, useRef } from 'react'

interface UseAutoRefreshOptions {
  callback: () => void | Promise<void>
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
  const callbackInFlightRef = useRef(false)

  const runCallback = useCallback(() => {
    if (callbackInFlightRef.current) {
      return
    }

    const result = callbackRef.current()

    if (result && typeof result.then === 'function') {
      callbackInFlightRef.current = true
      void result.then(
        () => {
          callbackInFlightRef.current = false
        },
        () => {
          callbackInFlightRef.current = false
        }
      )
    }
  }, [])

  // Update ref callback in a separate effect to avoid updating during render
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return

    // Run immediately on mount if requested
    if (runOnMount) {
      runCallback()
    }

    const interval = window.setInterval(() => {
      runCallback()
    }, intervalMs)

    return () => {
      if (interval) window.clearInterval(interval)
    }
  }, [enabled, intervalMs, runOnMount, runCallback])
}
