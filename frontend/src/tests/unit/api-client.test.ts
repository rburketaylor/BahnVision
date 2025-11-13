import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { config } from '../../lib/config'
import { apiClient, ApiError } from '../../services/api'

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

  it('builds query strings with repeated array params and drops nullish values', () => {
    const buildQueryString = (client as unknown as { buildQueryString: (params: Record<string, unknown>) => string })
      .buildQueryString

    const query = buildQueryString({
      station: 'de:09162:6',
      transport_type: ['UBAHN', 'BUS'],
      offset: 2,
      limit: null,
      extra: undefined,
    })

    expect(query).toBe('?station=de%3A09162%3A6&transport_type=UBAHN&transport_type=BUS&offset=2')
  })

  it('prevents planRoute calls with both departure and arrival times', async () => {
    await expect(
      client.planRoute({
        origin: 'A',
        destination: 'B',
        departure_time: '2024-01-01T10:00:00Z',
        arrival_time: '2024-01-01T11:00:00Z',
      })
    ).rejects.toBeInstanceOf(ApiError)

    expect(fetchMock).not.toHaveBeenCalled()
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
