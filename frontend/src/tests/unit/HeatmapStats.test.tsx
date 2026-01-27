import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HeatmapStats } from '../../components/heatmap/HeatmapStats'
import type { HeatmapSummary, HeatmapEnabledMetrics } from '../../types/heatmap'

describe('HeatmapStats', () => {
  const mockSummary: HeatmapSummary = {
    total_stations: 150,
    total_departures: 10000,
    total_cancellations: 350,
    overall_cancellation_rate: 0.035,
    total_delays: 500,
    overall_delay_rate: 0.05,
    most_affected_station: 'Marienplatz',
    most_affected_line: 'U-Bahn',
  }

  const defaultEnabledMetrics: HeatmapEnabledMetrics = {
    cancellations: true,
    delays: false,
  }

  it('renders loading state', () => {
    const { container } = render(
      <HeatmapStats summary={null} isLoading={true} enabledMetrics={defaultEnabledMetrics} />
    )

    expect(screen.getByText('Statistics')).toBeInTheDocument()
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(container.querySelectorAll('.bg-muted')).toHaveLength(5)
  })

  it('renders no data message when summary is null', () => {
    render(<HeatmapStats summary={null} isLoading={false} enabledMetrics={defaultEnabledMetrics} />)

    expect(screen.getByText('No data available')).toBeInTheDocument()
  })

  it('renders summary statistics', () => {
    render(<HeatmapStats summary={mockSummary} enabledMetrics={defaultEnabledMetrics} />)

    // Overall rate
    expect(screen.getByText('Overall Rate')).toBeInTheDocument()
    expect(screen.getByText('3.5%')).toBeInTheDocument()

    // Total departures
    expect(screen.getByText('Total Departures')).toBeInTheDocument()
    expect(screen.getByText('10,000')).toBeInTheDocument()

    // Cancellations
    expect(screen.getByText('Cancellations')).toBeInTheDocument()
    expect(screen.getByText('350')).toBeInTheDocument()

    // Stations
    expect(screen.getByText('Stations')).toBeInTheDocument()
    expect(screen.getByText('150')).toBeInTheDocument()
  })

  it('renders most affected station', () => {
    render(<HeatmapStats summary={mockSummary} enabledMetrics={defaultEnabledMetrics} />)

    expect(screen.getByText('Most Affected Station')).toBeInTheDocument()
    expect(screen.getByText('Marienplatz')).toBeInTheDocument()
  })

  it('renders most affected line', () => {
    render(<HeatmapStats summary={mockSummary} enabledMetrics={defaultEnabledMetrics} />)

    expect(screen.getByText('Most Affected Line')).toBeInTheDocument()
    expect(screen.getByText('U-Bahn')).toBeInTheDocument()
  })

  it('handles summary without affected station/line', () => {
    const summaryWithNulls: HeatmapSummary = {
      ...mockSummary,
      most_affected_station: null,
      most_affected_line: null,
    }

    render(<HeatmapStats summary={summaryWithNulls} enabledMetrics={defaultEnabledMetrics} />)

    // Should still render basic stats
    expect(screen.getByText('Total Departures')).toBeInTheDocument()
    // Should not render affected station/line sections
    expect(screen.queryByText('Most Affected Station')).not.toBeInTheDocument()
    expect(screen.queryByText('Most Affected Line')).not.toBeInTheDocument()
  })

  it('shows high rate with critical color', () => {
    const highRateSummary: HeatmapSummary = {
      ...mockSummary,
      overall_cancellation_rate: 0.08, // 8%
    }

    render(<HeatmapStats summary={highRateSummary} enabledMetrics={defaultEnabledMetrics} />)

    const rateValue = screen.getByText('8.0%')
    expect(rateValue).toBeInTheDocument()
    expect(rateValue).toHaveClass('text-status-critical')
  })

  it('shows moderate rate with warning color', () => {
    const moderateRateSummary: HeatmapSummary = {
      ...mockSummary,
      overall_cancellation_rate: 0.03, // 3%
    }

    render(<HeatmapStats summary={moderateRateSummary} enabledMetrics={defaultEnabledMetrics} />)

    const rateValue = screen.getByText('3.0%')
    expect(rateValue).toBeInTheDocument()
    expect(rateValue).toHaveClass('text-status-warning')
  })

  it('displays delay rate when only delays enabled', () => {
    render(
      <HeatmapStats summary={mockSummary} enabledMetrics={{ cancellations: false, delays: true }} />
    )

    const rateValue = screen.getByText('5.0%')
    expect(rateValue).toBeInTheDocument()
    expect(rateValue).toHaveClass('text-status-healthy')
    expect(screen.getByText('delays')).toBeInTheDocument()
  })

  it('displays combined rate when both metrics enabled', () => {
    render(
      <HeatmapStats summary={mockSummary} enabledMetrics={{ cancellations: true, delays: true }} />
    )

    // Combined rate = 3.5% + 5% = 8.5%
    const rateValue = screen.getByText('8.5%')
    expect(rateValue).toBeInTheDocument()
    expect(screen.getByText('combined')).toBeInTheDocument()
  })
})
