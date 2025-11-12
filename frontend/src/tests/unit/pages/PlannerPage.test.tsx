import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PlannerPage from '../../../pages/PlannerPage'

describe('PlannerPage', () => {
  it('renders planner headline and placeholder', () => {
    render(<PlannerPage />)
    expect(screen.getByText('Route Planner')).toBeInTheDocument()
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument()
  })
})
