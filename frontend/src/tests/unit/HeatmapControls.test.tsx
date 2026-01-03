import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HeatmapControls } from '../../components/heatmap/HeatmapControls'
import type { TransportType } from '../../types/api'
import type { TimeRangePreset, HeatmapEnabledMetrics } from '../../types/heatmap'

describe('HeatmapControls', () => {
  const defaultProps = {
    timeRange: '24h' as TimeRangePreset,
    onTimeRangeChange: vi.fn(),
    selectedTransportModes: [] as TransportType[],
    onTransportModesChange: vi.fn(),
    enabledMetrics: { cancellations: true, delays: true } as HeatmapEnabledMetrics,
    onEnabledMetricsChange: vi.fn(),
    isLive: true,
    onLiveChange: vi.fn(),
  }

  it('renders time range buttons', () => {
    render(<HeatmapControls {...defaultProps} />)

    expect(screen.getByText('Last hour')).toBeInTheDocument()
    expect(screen.getByText('Last 6 hours')).toBeInTheDocument()
    expect(screen.getByText('Last 24 hours')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
  })

  it('renders transport mode buttons', () => {
    render(<HeatmapControls {...defaultProps} />)

    expect(screen.getByText('U-Bahn')).toBeInTheDocument()
    expect(screen.getByText('S-Bahn')).toBeInTheDocument()
    expect(screen.getByText('Tram')).toBeInTheDocument()
    expect(screen.getByText('Bus')).toBeInTheDocument()
    expect(screen.getByText('Regional')).toBeInTheDocument()
  })

  it('calls onTimeRangeChange when time range button is clicked', () => {
    const onTimeRangeChange = vi.fn()
    render(<HeatmapControls {...defaultProps} onTimeRangeChange={onTimeRangeChange} />)

    fireEvent.click(screen.getByText('Last hour'))
    expect(onTimeRangeChange).toHaveBeenCalledWith('1h')

    fireEvent.click(screen.getByText('Last 7 days'))
    expect(onTimeRangeChange).toHaveBeenCalledWith('7d')
  })

  it('calls onTransportModesChange when transport button is clicked', () => {
    const onTransportModesChange = vi.fn()
    render(<HeatmapControls {...defaultProps} onTransportModesChange={onTransportModesChange} />)

    fireEvent.click(screen.getByText('U-Bahn'))
    expect(onTransportModesChange).toHaveBeenCalledWith(['UBAHN'])
  })

  it('removes transport mode when already selected', () => {
    const onTransportModesChange = vi.fn()
    render(
      <HeatmapControls
        {...defaultProps}
        selectedTransportModes={['UBAHN', 'SBAHN']}
        onTransportModesChange={onTransportModesChange}
      />
    )

    fireEvent.click(screen.getByText('U-Bahn'))
    expect(onTransportModesChange).toHaveBeenCalledWith(['SBAHN'])
  })

  it('selects all modes when All button is clicked', () => {
    const onTransportModesChange = vi.fn()
    render(<HeatmapControls {...defaultProps} onTransportModesChange={onTransportModesChange} />)

    fireEvent.click(screen.getByText('All'))
    expect(onTransportModesChange).toHaveBeenCalledWith(['UBAHN', 'SBAHN', 'TRAM', 'BUS', 'BAHN'])
  })

  it('clears all modes when None button is clicked', () => {
    const onTransportModesChange = vi.fn()
    render(
      <HeatmapControls
        {...defaultProps}
        selectedTransportModes={['UBAHN', 'SBAHN']}
        onTransportModesChange={onTransportModesChange}
      />
    )

    fireEvent.click(screen.getByText('None'))
    expect(onTransportModesChange).toHaveBeenCalledWith([])
  })

  it('disables buttons when loading', () => {
    render(<HeatmapControls {...defaultProps} isLoading={true} />)

    // Metric toggle buttons should be disabled
    expect(screen.getByText('Cancellations')).toBeDisabled()
    expect(screen.getByText('Delays')).toBeDisabled()

    // Time range buttons should be disabled
    expect(screen.getByText('Last hour')).toBeDisabled()
    expect(screen.getByText('Last 24 hours')).toBeDisabled()

    // Transport mode buttons should be disabled
    expect(screen.getByText('U-Bahn')).toBeDisabled()
    expect(screen.getByText('S-Bahn')).toBeDisabled()
  })

  it('shows message when no transport modes selected', () => {
    render(<HeatmapControls {...defaultProps} selectedTransportModes={[]} />)

    expect(screen.getByText('Showing all transport types')).toBeInTheDocument()
  })

  it('renders metric toggle buttons and calls onEnabledMetricsChange', () => {
    const onEnabledMetricsChange = vi.fn()
    render(
      <HeatmapControls
        {...defaultProps}
        enabledMetrics={{ cancellations: true, delays: true }}
        onEnabledMetricsChange={onEnabledMetricsChange}
      />
    )

    expect(screen.getByText('Cancellations')).toBeInTheDocument()
    expect(screen.getByText('Delays')).toBeInTheDocument()

    // Toggle delays off (should still have cancellations on)
    fireEvent.click(screen.getByText('Delays'))
    expect(onEnabledMetricsChange).toHaveBeenCalledWith({ cancellations: true, delays: false })
  })

  it('shows combined message when both metrics are enabled', () => {
    render(
      <HeatmapControls {...defaultProps} enabledMetrics={{ cancellations: true, delays: true }} />
    )

    expect(screen.getByText('Showing combined cancellation & delay intensity')).toBeInTheDocument()
  })

  it('prevents disabling both metrics', () => {
    const onEnabledMetricsChange = vi.fn()
    render(
      <HeatmapControls
        {...defaultProps}
        enabledMetrics={{ cancellations: true, delays: false }}
        onEnabledMetricsChange={onEnabledMetricsChange}
      />
    )

    // Try to toggle off the only enabled metric (cancellations)
    fireEvent.click(screen.getByText('Cancellations'))
    // Should not be called because it would disable both
    expect(onEnabledMetricsChange).not.toHaveBeenCalled()
  })

  describe('Live Mode', () => {
    it('renders live mode toggle showing "Live" when enabled', () => {
      render(<HeatmapControls {...defaultProps} isLive={true} />)

      expect(screen.getByText('Live')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /live/i, pressed: true })).toBeInTheDocument()
    })

    it('renders live mode toggle showing "Paused" when disabled', () => {
      render(<HeatmapControls {...defaultProps} isLive={false} />)

      expect(screen.getByText('Paused')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /paused/i, pressed: false })).toBeInTheDocument()
    })

    it('calls onLiveChange when live toggle is clicked', () => {
      const onLiveChange = vi.fn()
      render(<HeatmapControls {...defaultProps} isLive={true} onLiveChange={onLiveChange} />)

      fireEvent.click(screen.getByText('Live'))
      expect(onLiveChange).toHaveBeenCalledWith(false)
    })

    it('toggles from paused to live when clicked', () => {
      const onLiveChange = vi.fn()
      render(<HeatmapControls {...defaultProps} isLive={false} onLiveChange={onLiveChange} />)

      fireEvent.click(screen.getByText('Paused'))
      expect(onLiveChange).toHaveBeenCalledWith(true)
    })

    it('displays last updated time when provided', () => {
      const fiveMinutesAgo = Date.now() - 5 * 60 * 1000
      render(<HeatmapControls {...defaultProps} lastUpdatedAt={fiveMinutesAgo} />)

      expect(screen.getByText(/Last updated:/)).toBeInTheDocument()
      expect(screen.getByText(/5m ago/)).toBeInTheDocument()
    })

    it('displays "just now" for recent updates', () => {
      const justNow = Date.now() - 30 * 1000 // 30 seconds ago
      render(<HeatmapControls {...defaultProps} lastUpdatedAt={justNow} />)

      expect(screen.getByText(/just now/)).toBeInTheDocument()
    })

    it('shows auto-refresh message when live mode is enabled', () => {
      const recentTime = Date.now() - 60 * 1000
      render(<HeatmapControls {...defaultProps} isLive={true} lastUpdatedAt={recentTime} />)

      expect(screen.getByText(/Auto-refresh in 5 min/)).toBeInTheDocument()
    })

    it('does not show auto-refresh message when paused', () => {
      const recentTime = Date.now() - 60 * 1000
      render(<HeatmapControls {...defaultProps} isLive={false} lastUpdatedAt={recentTime} />)

      expect(screen.queryByText(/Auto-refresh in 5 min/)).not.toBeInTheDocument()
    })

    it('disables live toggle when loading', () => {
      render(<HeatmapControls {...defaultProps} isLoading={true} />)

      expect(screen.getByText('Live')).toBeDisabled()
    })
  })
})
