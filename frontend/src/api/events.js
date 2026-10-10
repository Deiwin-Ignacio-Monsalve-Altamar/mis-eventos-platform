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

/** List only events owned by the authenticated account. */
export async function listMyEvents({ page = 1, pageSize = 20, query = '', status = '' } = {}) {
  const parameters = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (query.trim()) parameters.set('q', query.trim())
  if (status) parameters.set('status', status)
  return request(`/events/mine?${parameters.toString()}`)
}

/** Retrieve an event through the authenticated owner-only management route. */
export async function getMyEvent(eventId) {
  const response = await request(`/events/mine/${encodeURIComponent(eventId)}`)
  return response.event
}

/** Read aggregate event activity for the authenticated creator. */
export async function getMyEventDashboard() {
  const response = await request('/events/mine/summary')
  return response.summary
}

/** Retrieve one event by its path identifier. */
export async function getEvent(eventId) {
  const response = await request(`/events/${encodeURIComponent(eventId)}`)
  return response.event
}

/** Read active attendee occupancy for a public event. */
export async function getEventCapacity(eventId) {
  return request(`/events/${encodeURIComponent(eventId)}/capacity`)
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

/** Update an event with the resource version required by the backend. */
export async function updateEvent(eventId, event) {
  const response = await request(`/events/${encodeURIComponent(eventId)}`, {
    method: 'PATCH',
    body: event,
  })
  return response.event
}

/** Delete an event through the authenticated endpoint. */
export async function deleteEvent(eventId) {
  return request(`/events/${encodeURIComponent(eventId)}`, {
    method: 'DELETE',
  })
}
