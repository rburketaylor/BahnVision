import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PlannerPage from '../../../pages/PlannerPage'

describe('PlannerPage', () => {
  it('renders planner headline and plan route action', () => {
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <PlannerPage />
      </QueryClientProvider>
    )
    expect(screen.getByText('Route Planner')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /plan route/i })).toBeInTheDocument()
  })
})
