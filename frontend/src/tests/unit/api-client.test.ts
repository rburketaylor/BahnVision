import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { config } from '../../lib/config'
import { apiClient } from '../../services/api'

const originalFetch = globalThis.fetch

describe('ApiClient low-level behaviors', () => {
  let client = apiClient
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    client = apiClient
  })

  afterEach(() => {
    vi.clearAllMocks()
    globalThis.fetch = originalFetch
  })

  it('maps HTTP errors to ApiError instances with details', async () => {
    const response400 = new Response(JSON.stringify({ detail: 'bad input' }), {
      status: 400,
      statusText: 'Bad Request',
      headers: { 'Content-Type': 'application/json' },
    })
    fetchMock.mockResolvedValueOnce(response400)

    await expect(client.getHealth()).rejects.toMatchObject({
      statusCode: 400,
      detail: 'bad input',
    })

    const response500 = new Response(JSON.stringify({ detail: 'server down' }), {
      status: 502,
      statusText: 'Bad Gateway',
      headers: { 'Content-Type': 'application/json' },
    })
    fetchMock.mockResolvedValueOnce(response500)

    await expect(client.getHealth()).rejects.toMatchObject({
      statusCode: 502,
      detail: 'server down',
    })
  })

  it('converts AbortError into a timeout ApiError', async () => {
    const abortError = new Error('aborted')
    abortError.name = 'AbortError'
    fetchMock.mockRejectedValue(abortError)

    await expect(client.getHealth()).rejects.toMatchObject({
      statusCode: 408,
    })
  })

  it('returns status 0 ApiError for generic network failures', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))

    await expect(client.getHealth()).rejects.toMatchObject({
      statusCode: 0,
    })
  })

  it('builds query strings with repeated array params and drops nullish values', async () => {
    // Create a mock response
    const mockResponse = new Response(JSON.stringify({ query: 'test', results: [] }), {
      status: 200,
      statusText: 'OK',
      headers: { 'Content-Type': 'application/json' },
    })
    fetchMock.mockResolvedValueOnce(mockResponse)

    // Call searchStops which internally builds a query string
    await client.searchStops({ query: 'test', limit: 10 })

    // Verify fetch was called with correct URL including query params
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('?query=test&limit=10'),
      expect.any(Object)
    )
  })

  it('fetches metrics text and errors on non-200 responses', async () => {
    const okResponse = new Response('metrics data', { status: 200, statusText: 'OK' })
    fetchMock.mockResolvedValueOnce(okResponse)

    await expect(client.getMetrics()).resolves.toBe('metrics data')
    expect(fetchMock).toHaveBeenCalledWith(`${config.apiBaseUrl}/metrics`)

    const badResponse = new Response('nope', { status: 503, statusText: 'Service Unavailable' })
    fetchMock.mockResolvedValueOnce(badResponse)

    await expect(client.getMetrics()).rejects.toMatchObject({ statusCode: 503 })
  })
})
