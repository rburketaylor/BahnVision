import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import Layout from '../../components/Layout'

describe('Layout', () => {
  it('renders navigation and highlights active route', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/planner']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<div>Departures Home</div>} />
            <Route path="/planner" element={<div>Planner Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Planner Content')).toBeInTheDocument()

    const plannerLink = screen.getByRole('link', { name: 'Planner' })
    expect(plannerLink.className).toContain('bg-primary/10')

    await user.click(screen.getByRole('link', { name: 'Departures' }))
    expect(screen.getByText('Departures Home')).toBeInTheDocument()
  })
})
