/** Verify the admin client uses the protected, paginated backend contracts. */

import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getAdminDashboard, listUsers, promoteUserToOrganizer } from '../../src/api/admin.js'

const originalFetch = globalThis.fetch

afterEach(() => { globalThis.fetch = originalFetch })

test('user search uses server pagination and cookie credentials', async () => {
  let actualUrl
  let options
  globalThis.fetch = async (url, requestOptions) => {
    actualUrl = url
    options = requestOptions
    return { ok: true, status: 200, json: async () => ({ users: [], pagination: { page: 2, page_size: 20, total: 0, total_pages: 0 } }) }
  }

  const result = await listUsers({ page: 2, pageSize: 20, query: ' Ada ' })

  assert.equal(actualUrl, '/api/v1/admin/users?page=2&page_size=20&q=Ada')
  assert.equal(options.credentials, 'include')
  assert.equal(result.pagination.page, 2)
})

test('promotion uses the existing operation and preserves authorization errors', async () => {
  let request
  globalThis.fetch = async (url, options) => {
    request = { url, options }
    return { ok: true, status: 200, json: async () => ({ user: { id: 8, role: 'ORGANIZER' } }) }
  }

  assert.deepEqual(await promoteUserToOrganizer(8), { id: 8, role: 'ORGANIZER' })
  assert.deepEqual(request, {
    url: '/api/v1/admin/users/8/promote-organizer',
    options: { method: 'POST', credentials: 'include', headers: {} },
  })

  globalThis.fetch = async () => ({
    ok: false,
    status: 403,
    json: async () => ({ error: { code: 'forbidden', message: 'Administrator role required.' } }),
  })
  await assert.rejects(promoteUserToOrganizer(8), (error) => error.status === 403 && error.code === 'forbidden')
})

test('administrator analytics use the protected dashboard endpoint', async () => {
  let actualUrl
  let credentials
  globalThis.fetch = async (url, options) => {
    actualUrl = url
    credentials = options.credentials
    return { ok: true, status: 200, json: async () => ({ dashboard: { summary: { users: { total: 5 } } } }) }
  }

  assert.deepEqual(await getAdminDashboard(), { summary: { users: { total: 5 } } })
  assert.equal(actualUrl, '/api/v1/admin/dashboard')
  assert.equal(credentials, 'include')
})
