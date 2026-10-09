/** Expose self-service event registration reads through the shared HTTP client. */

import { request } from './client.js'

/** List the authenticated user's registrations and event details for one page. */
export async function listMyRegistrations({ page = 1, pageSize = 20 } = {}) {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  return request(`/registrations/me?${parameters.toString()}`)
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
