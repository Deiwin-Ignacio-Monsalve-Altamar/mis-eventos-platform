/** Expose event operations using the existing event API response shapes. */

import { request } from './client.js'

/** List events with optional pagination and text search. */
export async function listEvents({ page = 1, pageSize = 20, query = '' } = {}) {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (query.trim()) {
    parameters.set('q', query.trim())
  }
  return request(`/events?${parameters.toString()}`)
}

/** Retrieve one event by its path identifier. */
export async function getEvent(eventId) {
  const response = await request(`/events/${encodeURIComponent(eventId)}`)
  return response.event
}

/** List the sessions attached to an event using the public nested route. */
export async function listEventSessions(eventId) {
  const response = await request(`/events/${encodeURIComponent(eventId)}/sessions`)
  return response.sessions
}

/** Read the backend's current session capacity and occupancy snapshot. */
export async function getSessionOccupancy(eventId, sessionId) {
  return request(
    `/events/${encodeURIComponent(eventId)}/sessions/${encodeURIComponent(sessionId)}/capacity`,
  )
}

/** Create an event using the current cookie-authenticated user. */
export async function createEvent(event) {
  const response = await request('/events', {
    method: 'POST',
    body: event,
  })
  return response.event
}
