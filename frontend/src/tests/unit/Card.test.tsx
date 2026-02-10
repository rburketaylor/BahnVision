import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Card } from '../../components/shared/Card'

describe('Card', () => {
  it('renders children with default styling', () => {
    render(
      <Card>
        <div>Content</div>
      </Card>
    )

    expect(screen.getByText('Content')).toBeInTheDocument()
    const card = screen.getByText('Content').closest('.card-base')
    expect(card).toBeInTheDocument()
    expect(card).toHaveClass('p-4')
  })

  it('applies accent, spacious padding, and custom classes', () => {
    const { container: normal } = render(
      <Card accent="blue" padding="spacious" className="custom-class">
        Content
      </Card>
    )
    expect(normal.firstChild).toHaveClass('card-accent-blue')
    expect(normal.firstChild).toHaveClass('p-5')
    expect(normal.firstChild).toHaveClass('custom-class')
  })

  it('applies noHover overrides when requested', () => {
    const { container } = render(
      <Card accent="green" noHover={true}>
        Content
      </Card>
    )

    expect(container.firstChild).toHaveClass('card-accent-green')
    expect(container.firstChild).toHaveClass('p-4')
    expect(container.firstChild).toHaveClass('hover:translate-y-0')
    expect(container.firstChild).toHaveClass('hover:shadow-surface-1')
    expect(container.firstChild).toHaveClass('hover:border-border')
  })
})
