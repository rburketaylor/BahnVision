import { type ReactElement } from 'react'
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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
        retryDelay: 1, // Minimal delay for tests
      },
    },
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('StationSearch', () => {
  beforeAll(() => server.listen())

  afterEach(() => {
    server.resetHandlers()
    localStorage.clear()
  })

  afterAll(() => server.close())

  it('shows stop results and selects a stop', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()
    const handleSelect = vi.fn()

    renderWithProviders(<StationSearch onSelect={handleSelect} />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Marien')
    await waitFor(() => expect(input).toHaveValue('Marien'))

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())

    const options = await screen.findAllByRole('option')
    const firstOption = options[0]

    expect(firstOption).toHaveTextContent(/Marienplatz/i)

    const optionButton = within(firstOption).getByRole('button', { name: /marien\s?platz/i })
    await user.click(optionButton)

    expect(handleSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'de:09162:6', name: 'Marienplatz' })
    )
    expect(input).toHaveValue('Marienplatz')
  })

  it('handles no results (404) response gracefully', async () => {
    server.use(
      http.get(`${BASE_URL}/api/v1/transit/stops/search`, () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 })
      )
    )

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Unknown station')

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    expect(
      await screen.findByRole('option', { name: /no stations found matching "Unknown station"/i })
    ).toBeInTheDocument()
  })

  it('surfaces API errors and allows retry', async () => {
    const errorHandler = vi.fn()

    server.use(
      http.get(`${BASE_URL}/api/v1/transit/stops/search`, () => {
        errorHandler()
        return HttpResponse.json({ detail: 'Bad request' }, { status: 400 })
      })
    )

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Marien')

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    // Look for error state - the component shows an error message
    expect(await screen.findByText(/error occurred|try again/i)).toBeInTheDocument()
    expect(errorHandler).toHaveBeenCalledTimes(1)

    // Reset handler to return success
    server.use(
      http.get(`${BASE_URL}/api/v1/transit/stops/search`, ({ request }) => {
        const url = new URL(request.url)
        const queryParam = url.searchParams.get('query') ?? ''
        return HttpResponse.json(
          {
            query: queryParam,
            results: [
              {
                id: 'de:09162:6',
                name: 'Marienplatz',
                latitude: 48.137079,
                longitude: 11.575447,
                zone_id: 'M',
                wheelchair_boarding: 1,
              },
            ],
          },
          { status: 200 }
        )
      })
    )

    const retryButton = await screen.findByRole('button', { name: /try again/i })
    await user.click(retryButton)

    const options = await screen.findAllByRole('option')
    const firstOption = options[0]
    expect(firstOption).toHaveTextContent(/Marienplatz/i)

    const optionButton = within(firstOption).getByRole('button', { name: /marien\s?platz/i })
    expect(optionButton).toBeInTheDocument()
  })

  it('clears recent searches from storage and UI', async () => {
    const user = userEvent.setup()

    localStorage.setItem(
      'bahnvision-recent-searches',
      JSON.stringify([
        {
          id: 'de:09162:6',
          name: 'Marienplatz',
          latitude: 48.137079,
          longitude: 11.575447,
          zone_id: 'M',
          wheelchair_boarding: 1,
          timestamp: Date.now() - 1_000,
        },
      ])
    )

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.click(input)

    expect(await screen.findByText(/recent searches/i)).toBeInTheDocument()
    expect(screen.getByText(/marienplatz/i)).toBeInTheDocument()

    const clearButton = screen.getByRole('button', { name: /clear all/i })
    await user.click(clearButton)

    await waitFor(() => expect(localStorage.getItem('bahnvision-recent-searches')).toBeNull())
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
