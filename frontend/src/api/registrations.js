/** Expose self-service event registration reads through the shared HTTP client. */

import { request } from './client.js'

/** List the authenticated user's registrations and event details for one page. */
export async function listMyRegistrations({ page = 1, pageSize = 20, status = '', period = '' } = {}) {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (status) parameters.set('status', status)
  if (period) parameters.set('period', period)
  return request(`/registrations/me?${parameters.toString()}`)
}

/** Read activity counts for the authenticated user's own event registrations. */
export async function getMyRegistrationSummary() {
  const response = await request('/registrations/me/summary')
  return response.summary
}

/** Find this user's registration for an event across the real paginated API. */
export async function findMyEventRegistration(eventId) {
  let page = 1
  let totalPages = 1

  while (page <= totalPages) {
    const result = await listMyRegistrations({ page, pageSize: 100 })
    const registration = result.registrations.find(
      (item) => item.event.id === Number(eventId),
    )
    if (registration) return registration

    totalPages = result.pagination.total_pages
    page += 1
  }

  return null
}

/** Register the authenticated user through the existing event endpoint. */
export async function registerForEvent(eventId) {
  return request(`/events/${encodeURIComponent(eventId)}/registrations/me`, {
    method: 'POST',
  })
}

/** Cancel only the authenticated user's own registration for an event. */
export async function cancelMyEventRegistration(eventId) {
  return request(`/events/${encodeURIComponent(eventId)}/registrations/me`, {
    method: 'DELETE',
  })
}
