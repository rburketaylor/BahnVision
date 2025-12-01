/**
 * Tests for CancellationHeatmap component
 * Validates layer configuration and rendering
 *
 * Note: Tests requiring leaflet.heat (canvas) are skipped in jsdom environment
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { CancellationHeatmap } from '../../components/heatmap/CancellationHeatmap'

// Mock canvas for leaflet.heat which requires HTMLCanvasElement.getContext
beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = () => null
})

describe('CancellationHeatmap Component', () => {
  it('should show loading state when isLoading is true', () => {
    render(<CancellationHeatmap dataPoints={[]} isLoading={true} />)

    expect(screen.getByText('Loading heatmap data...')).toBeInTheDocument()
  })

  it('should not show loading overlay when isLoading is false', () => {
    render(<CancellationHeatmap dataPoints={[]} isLoading={false} />)

    expect(screen.queryByText('Loading heatmap data...')).not.toBeInTheDocument()
  })
})
