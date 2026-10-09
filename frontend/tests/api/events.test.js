/** Verify public event discovery and self-service enrollment match backend contracts. */

import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getEvent, getSessionOccupancy, listEventSessions, listEvents } from '../../src/api/events.js'
import { findMyEventRegistration, registerForEvent } from '../../src/api/registrations.js'

const originalFetch = globalThis.fetch

/** Restore the shared fetch mock after each API contract test. */
function restoreFetch() {
  globalThis.fetch = originalFetch
}

afterEach(restoreFetch)

test('event listing sends real search and pagination parameters', async () => {
  let url
  globalThis.fetch = async (requestUrl) => {
    url = requestUrl
    return { ok: true, status: 200, json: async () => ({ events: [], pagination: { page: 2, page_size: 9, total: 0, total_pages: 0 } }) }
  }

  const response = await listEvents({ query: ' jazz ', page: 2, pageSize: 9 })
  assert.equal(url, '/api/v1/events?page=2&page_size=9&q=jazz')
  assert.equal(response.pagination.page, 2)
})

test('event detail, sessions, and public capacity use their documented routes', async () => {
  const requestedUrls = []
  globalThis.fetch = async (url) => {
    requestedUrls.push(url)
    const data = url.endsWith('/sessions')
      ? { sessions: [{ id: 3 }] }
      : url.endsWith('/capacity')
        ? { capacity: 20, occupied: 4, available: 16 }
        : { event: { id: 42 } }
    return { ok: true, status: 200, json: async () => data }
  }

  assert.deepEqual(await getEvent(42), { id: 42 })
  assert.deepEqual(await listEventSessions(42), [{ id: 3 }])
  assert.deepEqual(await getSessionOccupancy(42, 3), { capacity: 20, occupied: 4, available: 16 })
  assert.deepEqual(requestedUrls, [
    '/api/v1/events/42',
    '/api/v1/events/42/sessions',
    '/api/v1/events/42/sessions/3/capacity',
  ])
})

test('current-user registration lookup follows backend pagination and registration posts to its real endpoint', async () => {
  const requestedUrls = []
  let postOptions
  globalThis.fetch = async (url, options = {}) => {
    requestedUrls.push(url)
    if (options.method === 'POST') {
      postOptions = options
      return { ok: true, status: 201, json: async () => ({ registration: { id: 8, event_id: 42, status: 'registered' } }) }
    }
    const page = Number(new URL(url, 'http://localhost').searchParams.get('page'))
    return {
      ok: true,
      status: 200,
      json: async () => ({
        registrations: page === 2 ? [{ status: 'registered', event: { id: 42 } }] : [],
        pagination: { page, page_size: 100, total: 101, total_pages: 2 },
      }),
    }
  }

  assert.deepEqual(await findMyEventRegistration(42), { status: 'registered', event: { id: 42 } })
  assert.equal(requestedUrls[0], '/api/v1/registrations/me?page=1&page_size=100')
  assert.equal(requestedUrls[1], '/api/v1/registrations/me?page=2&page_size=100')
  assert.deepEqual(await registerForEvent(42), { registration: { id: 8, event_id: 42, status: 'registered' } })
  assert.equal(requestedUrls[2], '/api/v1/events/42/registrations/me')
  assert.equal(postOptions.method, 'POST')
  assert.equal(postOptions.credentials, 'include')
})
