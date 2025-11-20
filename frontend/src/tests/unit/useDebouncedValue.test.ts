import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the initial value immediately', () => {
    const { result } = renderHook(({ value, delay }) => useDebouncedValue(value, delay), {
      initialProps: { value: 'Marienplatz', delay: 300 },
    })

    expect(result.current).toBe('Marienplatz')
  })

  it('updates the value after the specified delay', () => {
    const { result, rerender } = renderHook(({ value, delay }) => useDebouncedValue(value, delay), {
      initialProps: { value: 'Marien', delay: 300 },
    })

    rerender({ value: 'Marienp', delay: 300 })
    expect(result.current).toBe('Marien')

    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(result.current).toBe('Marien')

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current).toBe('Marienp')
  })
})
