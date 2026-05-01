import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAutoRefresh } from './useAutoRefresh'

function createDeferred() {
  let resolve: () => void = () => {}
  let reject: (error?: unknown) => void = () => {}
  const promise = new Promise<void>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAutoRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('runs on mount and at the configured interval', () => {
    const callback = vi.fn()

    renderHook(() =>
      useAutoRefresh({
        callback,
        intervalMs: 1000,
        runOnMount: true,
      })
    )

    expect(callback).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(callback).toHaveBeenCalledTimes(4)
  })

  it('prevents overlapping async callback executions', async () => {
    const firstRun = createDeferred()
    const secondRun = createDeferred()

    const callback = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(() => firstRun.promise)
      .mockImplementationOnce(() => secondRun.promise)

    renderHook(() =>
      useAutoRefresh({
        callback,
        intervalMs: 1000,
        runOnMount: true,
      })
    )

    expect(callback).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(callback).toHaveBeenCalledTimes(1)

    await act(async () => {
      firstRun.resolve()
      await Promise.resolve()
    })

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(callback).toHaveBeenCalledTimes(2)

    await act(async () => {
      secondRun.resolve()
      await Promise.resolve()
    })
  })

  it('allows retries after async callback rejects', async () => {
    const firstRun = createDeferred()
    const secondRun = createDeferred()

    const callback = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(() => firstRun.promise)
      .mockImplementationOnce(() => secondRun.promise)

    renderHook(() =>
      useAutoRefresh({
        callback,
        intervalMs: 1000,
        runOnMount: true,
      })
    )

    expect(callback).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(callback).toHaveBeenCalledTimes(1)

    await act(async () => {
      firstRun.reject(new Error('fail'))
      await Promise.resolve()
    })

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(callback).toHaveBeenCalledTimes(2)

    await act(async () => {
      secondRun.resolve()
      await Promise.resolve()
    })
  })
})
