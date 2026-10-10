/** Verify public event discovery and self-service enrollment match backend contracts. */

import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { createEvent, createEventSession, deleteEvent, deleteEventSession, getEvent, getEventCapacity, getMyEvent, getMyEventDashboard, getSessionOccupancy, listEventSessions, listEvents, listMyEvents, updateEvent, updateEventSession } from '../../src/api/events.js'
import { cancelMyEventRegistration, findMyEventRegistration, getMyRegistrationSummary, listMyRegistrations, registerForEvent } from '../../src/api/registrations.js'

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

test('personal event queries use authenticated owner routes and supported filters', async () => {
  const urls = []
  globalThis.fetch = async (url) => {
    urls.push(url)
    return { ok: true, status: 200, json: async () => url.includes('/summary')
      ? { summary: { total_events: 0 } }
      : { events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 }, event: { id: 42 } } }
  }

  await listMyEvents({ page: 2, pageSize: 9, query: 'meetup', status: 'draft' })
  assert.deepEqual(await getMyEvent(42), { id: 42 })
  assert.deepEqual(await getMyEventDashboard(), { total_events: 0 })
  assert.deepEqual(urls, [
    '/api/v1/events/mine?page=2&page_size=9&q=meetup&status=draft',
    '/api/v1/events/mine/42',
    '/api/v1/events/mine/summary',
  ])
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
  assert.deepEqual(await getEventCapacity(42), { capacity: 20, occupied: 4, available: 16 })
  assert.deepEqual(await listEventSessions(42), [{ id: 3 }])
  assert.deepEqual(await getSessionOccupancy(42, 3), { capacity: 20, occupied: 4, available: 16 })
  assert.deepEqual(requestedUrls, [
    '/api/v1/events/42',
    '/api/v1/events/42/capacity',
    '/api/v1/events/42/sessions',
    '/api/v1/events/42/sessions/3/capacity',
  ])
})

/** Verify the session mutations use only the backend's existing nested routes. */
test('session create, update, and delete use the existing event-scoped API contracts', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method, body: options.body })
    return options.method === 'DELETE'
      ? { ok: true, status: 204, json: async () => null }
      : { ok: true, status: options.method === 'POST' ? 201 : 200, json: async () => ({ session: { id: 7, title: 'Opening talk' } }) }
  }
  const values = { title: 'Opening talk', capacity: 20, speaker_ids: [], version: 2 }

  assert.deepEqual(await createEventSession(42, values), { id: 7, title: 'Opening talk' })
  assert.deepEqual(await updateEventSession(42, 7, values), { id: 7, title: 'Opening talk' })
  await deleteEventSession(42, 7)
  assert.deepEqual(calls, [
    { url: '/api/v1/events/42/sessions', method: 'POST', body: JSON.stringify(values) },
    { url: '/api/v1/events/42/sessions/7', method: 'PATCH', body: JSON.stringify(values) },
    { url: '/api/v1/events/42/sessions/7', method: 'DELETE', body: undefined },
  ])
})

/** Preserve backend errors so failed session writes cannot appear successful. */
test('session mutation failures remain API errors', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 409,
    json: async () => ({ error: { code: 'concurrency_conflict', message: 'Session changed.' } }),
  })

  await assert.rejects(updateEventSession(42, 7, { title: 'Stale', version: 1 }), (error) => {
    assert.equal(error.status, 409)
    assert.equal(error.code, 'concurrency_conflict')
    return true
  })
})

test('event creation posts the backend event fields to the authenticated route', async () => {
  let requestUrl
  let requestOptions
  globalThis.fetch = async (url, options) => {
    requestUrl = url
    requestOptions = options
    return { ok: true, status: 201, json: async () => ({ event: { id: 42, title: 'Forum' } }) }
  }
  const payload = {
    title: 'Forum',
    starts_at: '2030-01-01T10:00:00Z',
    ends_at: '2030-01-01T12:00:00Z',
    capacity: 25,
    status: 'draft',
  }

  assert.deepEqual(await createEvent(payload), { id: 42, title: 'Forum' })
  assert.equal(requestUrl, '/api/v1/events')
  assert.equal(requestOptions.method, 'POST')
  assert.deepEqual(JSON.parse(requestOptions.body), payload)
  assert.equal(requestOptions.credentials, 'include')
})

test('event updates send the required version and delete uses the real endpoint', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return options.method === 'PATCH'
      ? { ok: true, status: 200, json: async () => ({ event: { id: 42, title: 'Updated', version: 2 } }) }
      : { ok: true, status: 204, json: async () => null }
  }
  const updated = await updateEvent(42, { title: 'Updated', version: 1 })
  await deleteEvent(42)

  assert.deepEqual(updated, { id: 42, title: 'Updated', version: 2 })
  assert.equal(calls[0].url, '/api/v1/events/42')
  assert.equal(calls[0].options.method, 'PATCH')
  assert.deepEqual(JSON.parse(calls[0].options.body), { title: 'Updated', version: 1 })
  assert.equal(calls[1].url, '/api/v1/events/42')
  assert.equal(calls[1].options.method, 'DELETE')
  assert.equal(calls[1].options.credentials, 'include')
})

test('event update surfaces backend validation and concurrency errors', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 409,
    json: async () => ({
      error: {
        code: 'concurrency_conflict',
        message: 'The event has changed.',
        current_version: 3,
      },
    }),
  })

  await assert.rejects(updateEvent(42, { title: 'Stale', version: 1 }), (error) => {
    assert.equal(error.status, 409)
    assert.equal(error.code, 'concurrency_conflict')
    assert.equal(error.currentVersion, 3)
    return true
  })
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

test('registration filters, summary, and cancellation use current-user endpoints', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method || 'GET' })
    return { ok: true, status: options.method === 'DELETE' ? 204 : 200,
      json: async () => options.method === 'DELETE' ? null : { registrations: [], pagination: {}, summary: { active: 0 } } }
  }

  await listMyRegistrations({ status: 'registered', period: 'upcoming' })
  assert.deepEqual(await getMyRegistrationSummary(), { active: 0 })
  await cancelMyEventRegistration(42)

  assert.deepEqual(calls, [
    { url: '/api/v1/registrations/me?page=1&page_size=20&status=registered&period=upcoming', method: 'GET' },
    { url: '/api/v1/registrations/me/summary', method: 'GET' },
    { url: '/api/v1/events/42/registrations/me', method: 'DELETE' },
  ])
})
