import { describe, it, expect } from 'vitest'
import { getBVVGlowColor, getBVVMarkerColor } from '../../components/heatmap/markerStyles'

describe('markerStyles', () => {
  it('maps intensity to BVV marker colors', () => {
    expect(getBVVMarkerColor(0.9)).toBe('rgba(214, 15, 38, 1.0)')
    expect(getBVVMarkerColor(0.7)).toBe('rgba(214, 15, 38, 0.92)')
    expect(getBVVMarkerColor(0.5)).toBe('rgba(245, 158, 11, 0.90)')
    expect(getBVVMarkerColor(0.3)).toBe('rgba(245, 158, 11, 0.75)')
    expect(getBVVMarkerColor(0.1)).toBe('rgba(0, 171, 78, 0.75)')
  })

  it('maps intensity to BVV glow colors', () => {
    expect(getBVVGlowColor(0.9)).toBe('rgba(214, 15, 38, 0.32)')
    expect(getBVVGlowColor(0.7)).toBe('rgba(214, 15, 38, 0.28)')
    expect(getBVVGlowColor(0.5)).toBe('rgba(245, 158, 11, 0.28)')
    expect(getBVVGlowColor(0.3)).toBe('rgba(245, 158, 11, 0.20)')
    expect(getBVVGlowColor(0.1)).toBe('rgba(0, 171, 78, 0.20)')
  })
})
