import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Badge, TransportBadge } from '../../components/shared/Badge'

describe('Badge', () => {
  it('renders outline variant', () => {
    const { container } = render(
      <Badge variant="warning" outline={true}>
        Warn
      </Badge>
    )

    expect(screen.getByText('Warn')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('bg-transparent')
    expect(container.firstChild).toHaveClass('border')
  })

  it('renders TransportBadge fallback for unknown type', () => {
    const { container } = render(<TransportBadge type="FERRY" />)
    expect(container.firstChild).toHaveClass('bg-muted')
    expect(screen.getByText('F')).toBeInTheDocument()
  })
})
