/** Centralize API URL configuration, cookie credentials, and response errors. */

import { reportApiDuration, reportApiError } from '../observability.js'

const configuredBaseUrl = import.meta.env?.VITE_API_BASE_URL || '/api/v1'
const apiBaseUrl = configuredBaseUrl.replace(/\/+$/, '')

/** Describe an HTTP or network failure in a consistent application shape. */
export class ApiError extends Error {
  constructor(message, { status = null, code = 'request_failed', payload = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.payload = payload
    this.currentVersion = payload?.error?.current_version ?? null
  }
}

/** Make a cookie-authenticated request and return its parsed JSON response. */
export async function request(path, options = {}) {
  const { body, headers = {}, ...requestOptions } = options
  const startedAt = globalThis.performance?.now?.() ?? Date.now()
  const method = (requestOptions.method || 'GET').toUpperCase()
  let response

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...requestOptions,
      credentials: 'include',
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (error) {
    reportApiDuration(((globalThis.performance?.now?.() ?? Date.now()) - startedAt) / 1000, method)
    if (error?.name === 'AbortError') {
      throw error
    }
    const networkError = new ApiError('The server could not be reached.', {
      code: 'network_error',
    })
    reportApiError(networkError)
    throw networkError
  }

  reportApiDuration(((globalThis.performance?.now?.() ?? Date.now()) - startedAt) / 1000, method)
  const responsePayload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = responsePayload?.error
    const apiError = new ApiError(error?.message || `Request failed (${response.status}).`, {
      status: response.status,
      code: error?.code || 'http_error',
      payload: responsePayload,
    })
    reportApiError(apiError, response.status)
    throw apiError
  }

  return responsePayload
}
