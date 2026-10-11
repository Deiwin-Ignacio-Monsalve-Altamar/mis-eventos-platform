/** Provide administrator-only directory and role-promotion operations. */

import { request } from './client.js'

/** Request one server-filtered user directory page. */
export function listUsers({ page = 1, pageSize = 20, query = '' } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (query.trim()) params.set('q', query.trim())
  return request(`/admin/users?${params.toString()}`)
}

/** Retrieve real platform metrics through the administrator-only dashboard API. */
export async function getAdminDashboard() {
  const result = await request('/admin/dashboard')
  return result.dashboard
}

/** Promote one attendee through the existing administrator operation. */
export async function promoteUserToOrganizer(userId) {
  const result = await request(`/admin/users/${encodeURIComponent(userId)}/promote-organizer`, {
    method: 'POST',
  })
  return result.user
}
