import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Badge, TransportBadge } from '../../components/shared/Badge'

describe('Badge', () => {
  it('renders outline variant with warning semantics', () => {
    render(
      <Badge variant="warning" outline={true}>
        Warn
      </Badge>
    )

    const badge = screen.getByText('Warn')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-transparent')
    expect(badge).toHaveClass('border-status-warning/40')
    expect(badge).toHaveClass('text-status-warning')
    expect(badge).not.toHaveClass('bg-status-warning/14')
  })

  it('maps known transport types to circular labels', () => {
    render(<TransportBadge type="TRAM" small={true} />)

    const badge = screen.getByText('T')
    expect(badge).toHaveClass('rounded-full')
    expect(badge).toHaveClass('aspect-square')
    expect(badge).toHaveClass('bg-tram/90')
    expect(badge).toHaveClass('w-6')
    expect(badge).toHaveClass('h-6')
  })

  it('falls back to neutral variant and first letter for unknown transport type', () => {
    render(<TransportBadge type="FERRY" />)

    const badge = screen.getByText('F')
    expect(badge).toHaveClass('bg-surface-elevated')
    expect(badge).toHaveClass('text-muted-foreground')
    expect(badge).toHaveClass('rounded-full')
  })
})
