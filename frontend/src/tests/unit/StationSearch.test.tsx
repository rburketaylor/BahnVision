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
  })

  afterAll(() => server.close())

  it('shows station results and selects a station', async () => {
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

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()

    renderWithProviders(<StationSearch />)

    const input = screen.getByRole('combobox', { name: /station search/i })
    await user.type(input, 'Unknown station')

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    expect(await screen.findByRole('option', { name: /no stations found/i })).toBeInTheDocument()
  })

  it('surfaces API errors and allows retry', async () => {
    const errorHandler = vi.fn()

    server.use(
      http.get(`${BASE_URL}/api/v1/mvg/stations/search`, () => {
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
    expect(
      await screen.findByRole('option', { name: /unable to load stations/i })
    ).toBeInTheDocument()
    expect(errorHandler).toHaveBeenCalledTimes(1)

    server.use(
      http.get(`${BASE_URL}/api/v1/mvg/stations/search`, ({ request }) => {
        const url = new URL(request.url)
        const queryParam = url.searchParams.get('query') ?? ''
        return HttpResponse.json(
          {
            query: queryParam,
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

    const retryButton = await screen.findByRole('button', { name: /try again/i })
    await user.click(retryButton)

    const options = await screen.findAllByRole('option')
    const firstOption = options[0]
    expect(firstOption).toHaveTextContent(/Marienplatz/i)

    const optionButton = within(firstOption).getByRole('button', { name: /marien\s?platz/i })
    expect(optionButton).toBeInTheDocument()
  })
})
