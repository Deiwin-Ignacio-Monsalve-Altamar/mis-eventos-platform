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
