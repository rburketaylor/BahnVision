import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HeatmapControls } from '../../components/heatmap/HeatmapControls'
import type { TransportType } from '../../types/api'
import type { TimeRangePreset } from '../../types/heatmap'

describe('HeatmapControls', () => {
  const defaultProps = {
    timeRange: '24h' as TimeRangePreset,
    onTimeRangeChange: vi.fn(),
    selectedTransportModes: [] as TransportType[],
    onTransportModesChange: vi.fn(),
    metric: 'cancellations' as const,
    onMetricChange: vi.fn(),
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

    // Metric buttons should be disabled
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

  it('renders metric buttons and calls onMetricChange', () => {
    const onMetricChange = vi.fn()
    render(<HeatmapControls {...defaultProps} onMetricChange={onMetricChange} />)

    expect(screen.getByText('Cancellations')).toBeInTheDocument()
    expect(screen.getByText('Delays')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Delays'))
    expect(onMetricChange).toHaveBeenCalledWith('delays')
  })
})
