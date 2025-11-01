import { type ReactElement } from 'react'
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import StationSearch from '../../components/StationSearch'
import { server } from '../mocks/server'

const BASE_URL = 'http://localhost:8000'

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('StationSearch', () => {
  beforeAll(() => server.listen())

  afterEach(() => {
    server.resetHandlers()
    vi.useRealTimers()
  })

  afterAll(() => server.close())

  it('shows station results and selects a station', async () => {
    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const handleSelect = vi.fn()

    renderWithProviders(<StationSearch onSelect={handleSelect} />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Marien')
    await waitFor(() => expect(input).toHaveValue('Marien'))

    act(() => {
      vi.advanceTimersByTime(300)
    })

    const option = await screen.findByRole('option', { name: /marienplatz/i })
    expect(option).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /marienplatz/i }))

    expect(handleSelect).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Marienplatz', place: 'München' })
    )
    expect(input).toHaveValue('Marienplatz')
  })

  it('handles no results (404) response gracefully', async () => {
    server.use(
      http.get(`${BASE_URL}/api/v1/mvg/stations/search`, () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 })
      )
    )

    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Unknown station')

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(await screen.findByText(/No stations found/i)).toBeInTheDocument()
  })

  it('surfaces API errors and allows retry', async () => {
    const errorHandler = vi.fn()

    server.use(
      http.get(`${BASE_URL}/api/v1/mvg/stations/search`, () => {
        errorHandler()
        return HttpResponse.json({ detail: 'Service unavailable' }, { status: 503 })
      })
    )

    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Marien')

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(await screen.findByText(/Unable to load stations/i)).toBeInTheDocument()
    expect(errorHandler).toHaveBeenCalledTimes(1)

    server.use(
      http.get(`${BASE_URL}/api/v1/mvg/stations/search`, ({ request }) => {
        const url = new URL(request.url)
        const q = url.searchParams.get('q') ?? ''
        return HttpResponse.json(
          {
            query: q,
            results: [
              {
                id: 'de:09162:6',
                name: 'Marienplatz',
                place: 'München',
                latitude: 48.137079,
                longitude: 11.575447,
              },
            ],
          },
          { status: 200 }
        )
      })
    )

    await user.click(screen.getByRole('button', { name: /try again/i }))

    const option = await screen.findByRole('option', { name: /marienplatz/i })
    expect(option).toBeInTheDocument()
  })
})
