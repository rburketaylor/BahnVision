import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import PlannerPage from '../../../pages/PlannerPage'

describe('PlannerPage', () => {
  it('renders planner headline and coming soon message', () => {
    render(
      <MemoryRouter>
        <PlannerPage />
      </MemoryRouter>
    )
    expect(screen.getByText('Route Planner')).toBeInTheDocument()
    expect(screen.getByText('Coming Soon')).toBeInTheDocument()
  })
})
