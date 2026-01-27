import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HeatmapOverlayPanel } from '../../components/heatmap/HeatmapOverlayPanel'

describe('HeatmapOverlayPanel', () => {
  it('renders show button when closed and calls onOpenChange', () => {
    const onOpenChange = vi.fn()
    render(
      <HeatmapOverlayPanel
        open={false}
        onOpenChange={onOpenChange}
        title="Title"
        description="Desc"
        onRefresh={() => {}}
      >
        <div>Content</div>
      </HeatmapOverlayPanel>
    )

    fireEvent.click(screen.getByRole('button', { name: /show heatmap controls/i }))
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it('renders panel when open, triggers refresh and close', () => {
    const onOpenChange = vi.fn()
    const onRefresh = vi.fn()
    render(
      <HeatmapOverlayPanel
        open={true}
        onOpenChange={onOpenChange}
        title="Controls"
        description="Filter settings"
        onRefresh={onRefresh}
      >
        <div>Inner</div>
      </HeatmapOverlayPanel>
    )

    fireEvent.click(screen.getByRole('button', { name: /refresh heatmap data/i }))
    expect(onRefresh).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /hide heatmap controls/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('returns focus to show button when closing', async () => {
    const onOpenChange = vi.fn()
    const { rerender } = render(
      <HeatmapOverlayPanel
        open={true}
        onOpenChange={onOpenChange}
        title="Controls"
        description="Desc"
        onRefresh={() => {}}
      >
        <div>Inner</div>
      </HeatmapOverlayPanel>
    )

    rerender(
      <HeatmapOverlayPanel
        open={false}
        onOpenChange={onOpenChange}
        title="Controls"
        description="Desc"
        onRefresh={() => {}}
      >
        <div>Inner</div>
      </HeatmapOverlayPanel>
    )

    const showButton = screen.getByRole('button', { name: /show heatmap controls/i })
    await waitFor(() => expect(showButton).toHaveFocus())
  })
})
