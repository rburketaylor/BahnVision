import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Card } from '../../components/shared/Card'

describe('Card', () => {
  it('renders children with default styling', () => {
    const { container } = render(
      <Card>
        <div>Content</div>
      </Card>
    )

    expect(screen.getByText('Content')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('card-base')
  })

  it('applies accent, padding, and noHover variants', () => {
    const { container: normal } = render(
      <Card accent="blue" padding="spacious">
        Content
      </Card>
    )
    expect(normal.firstChild).toHaveClass('card-accent-blue')
    expect(normal.firstChild).toHaveClass('p-5')

    const { container: noHover } = render(
      <Card accent="green" noHover={true}>
        Content
      </Card>
    )
    expect(noHover.firstChild).toHaveClass('card-accent-green')
    expect(noHover.firstChild).toHaveClass('p-4')
  })
})
