/**
 * useDebouncedValue
 * Returns a debounced version of the provided value that updates after the delay.
 */

import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      window.clearTimeout(handle)
    }
  }, [value, delay])

  return debouncedValue
}
