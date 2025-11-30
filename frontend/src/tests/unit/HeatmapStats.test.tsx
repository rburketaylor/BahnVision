import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HeatmapStats } from '../../components/heatmap/HeatmapStats'
import type { HeatmapSummary } from '../../types/heatmap'

describe('HeatmapStats', () => {
  const mockSummary: HeatmapSummary = {
    total_stations: 150,
    total_departures: 10000,
    total_cancellations: 350,
    overall_cancellation_rate: 0.035,
    most_affected_station: 'Marienplatz',
    most_affected_line: 'U-Bahn',
  }

  it('renders loading state', () => {
    render(<HeatmapStats summary={null} isLoading={true} />)

    expect(screen.getByText('Statistics')).toBeInTheDocument()
    // Should show skeleton/loading state
  })

  it('renders no data message when summary is null', () => {
    render(<HeatmapStats summary={null} isLoading={false} />)

    expect(screen.getByText('No data available')).toBeInTheDocument()
  })

  it('renders summary statistics', () => {
    render(<HeatmapStats summary={mockSummary} />)

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
    render(<HeatmapStats summary={mockSummary} />)

    expect(screen.getByText('Most Affected Station')).toBeInTheDocument()
    expect(screen.getByText('Marienplatz')).toBeInTheDocument()
  })

  it('renders most affected line', () => {
    render(<HeatmapStats summary={mockSummary} />)

    expect(screen.getByText('Most Affected Line')).toBeInTheDocument()
    expect(screen.getByText('U-Bahn')).toBeInTheDocument()
  })

  it('handles summary without affected station/line', () => {
    const summaryWithNulls: HeatmapSummary = {
      ...mockSummary,
      most_affected_station: null,
      most_affected_line: null,
    }

    render(<HeatmapStats summary={summaryWithNulls} />)

    // Should still render basic stats
    expect(screen.getByText('Total Departures')).toBeInTheDocument()
    // Should not render affected station/line sections
    expect(screen.queryByText('Most Affected Station')).not.toBeInTheDocument()
    expect(screen.queryByText('Most Affected Line')).not.toBeInTheDocument()
  })

  it('shows high rate with red color', () => {
    const highRateSummary: HeatmapSummary = {
      ...mockSummary,
      overall_cancellation_rate: 0.08, // 8%
    }

    render(<HeatmapStats summary={highRateSummary} />)

    expect(screen.getByText('8.0%')).toBeInTheDocument()
  })

  it('shows moderate rate with yellow color', () => {
    const moderateRateSummary: HeatmapSummary = {
      ...mockSummary,
      overall_cancellation_rate: 0.03, // 3%
    }

    render(<HeatmapStats summary={moderateRateSummary} />)

    expect(screen.getByText('3.0%')).toBeInTheDocument()
  })
})
