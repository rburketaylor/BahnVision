import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import Layout from '../../components/Layout'
import { ThemeProvider } from '../../contexts/ThemeContext'

describe('Layout', () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }))
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it('renders navigation and highlights active route', async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/search']}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<div>Map Home</div>} />
              <Route path="/search" element={<div>Stations Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    )

    expect(screen.getByText('Stations Content')).toBeInTheDocument()

    const stationsLink = screen.getByRole('link', { name: 'Stations' })
    expect(stationsLink.className).toContain('bg-primary/10')

    await user.click(screen.getByRole('link', { name: 'Map' }))
    expect(screen.getByText('Map Home')).toBeInTheDocument()
  })
})
