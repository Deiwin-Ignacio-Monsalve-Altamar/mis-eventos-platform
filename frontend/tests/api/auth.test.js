/** Verify authentication services use the actual API routes and payloads. */

import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getCurrentUser, login, logout, registerAccount } from '../../src/api/auth.js'
import { listMyRegistrations } from '../../src/api/registrations.js'

const originalFetch = globalThis.fetch

/** Restore the global fetch implementation after each API contract test. */
function restoreFetch() {
  globalThis.fetch = originalFetch
}

afterEach(restoreFetch)

test('registration posts the backend fields and returns only the public user', async () => {
  let url
  let options
  globalThis.fetch = async (requestUrl, requestOptions) => {
    url = requestUrl
    options = requestOptions
    return { ok: true, status: 201, json: async () => ({ user: { id: 9, email: 'ari@example.test' } }) }
  }

  const user = await registerAccount({
    first_name: 'Ari',
    last_name: 'Rivera',
    email: 'ari@example.test',
    password: 'long-enough-password',
  })

  assert.equal(url, '/api/v1/auth/register')
  assert.equal(options.method, 'POST')
  assert.deepEqual(JSON.parse(options.body), {
    first_name: 'Ari',
    last_name: 'Rivera',
    email: 'ari@example.test',
    password: 'long-enough-password',
  })
  assert.deepEqual(user, { id: 9, email: 'ari@example.test' })
})

test('registration exposes duplicate-account conflicts through ApiError', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 409,
    json: async () => ({ error: { code: 'account_exists', message: 'An account with this email already exists.' } }),
  })

  await assert.rejects(registerAccount({}), (error) => {
    assert.equal(error.status, 409)
    assert.equal(error.code, 'account_exists')
    return true
  })
})

test('login posts credentials and returns the authenticated public user', async () => {
  let url
  let options
  globalThis.fetch = async (requestUrl, requestOptions) => {
    url = requestUrl
    options = requestOptions
    return { ok: true, status: 200, json: async () => ({ user: { id: 9, email: 'ari@example.test' } }) }
  }

  const user = await login({ email: 'ari@example.test', password: 'secret' })

  assert.equal(url, '/api/v1/auth/login')
  assert.equal(options.credentials, 'include')
  assert.deepEqual(JSON.parse(options.body), { email: 'ari@example.test', password: 'secret' })
  assert.deepEqual(user, { id: 9, email: 'ari@example.test' })
})

test('login preserves generic credential errors and network failures', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 401,
    json: async () => ({ error: { code: 'invalid_credentials', message: 'Email or password is incorrect.' } }),
  })
  await assert.rejects(login({ email: 'ari@example.test', password: 'wrong' }), (error) => {
    assert.equal(error.status, 401)
    assert.equal(error.code, 'invalid_credentials')
    assert.equal(error.message, 'Email or password is incorrect.')
    return true
  })

  globalThis.fetch = async () => { throw new TypeError('network unavailable') }
  await assert.rejects(login({ email: 'ari@example.test', password: 'secret' }), (error) => {
    assert.equal(error.code, 'network_error')
    return true
  })
})

test('session lookup uses the cookie-authenticated endpoint and distinguishes 401', async () => {
  let url
  globalThis.fetch = async (requestUrl) => {
    url = requestUrl
    return { ok: false, status: 401, json: async () => ({ error: { code: 'authentication_required', message: 'Authentication is required.' } }) }
  }

  await assert.rejects(getCurrentUser(), (error) => {
    assert.equal(url, '/api/v1/auth/me')
    assert.equal(error.status, 401)
    return true
  })
})

test('logout expires the server cookie through the authentication endpoint', async () => {
  let url
  let options
  globalThis.fetch = async (requestUrl, requestOptions) => {
    url = requestUrl
    options = requestOptions
    return { ok: true, status: 204, json: async () => null }
  }

  await logout()

  assert.equal(url, '/api/v1/auth/logout')
  assert.equal(options.method, 'POST')
  assert.equal(options.credentials, 'include')
})

test('logout failures remain API errors and do not report success', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ error: { code: 'authentication_unavailable', message: 'Authentication unavailable.' } }),
  })

  await assert.rejects(logout(), (error) => {
    assert.equal(error.status, 503)
    assert.equal(error.code, 'authentication_unavailable')
    return true
  })
})

test('own-registration lookup uses the authenticated route and pagination contract', async () => {
  let url
  let options
  globalThis.fetch = async (requestUrl, requestOptions) => {
    url = requestUrl
    options = requestOptions
    return {
      ok: true,
      status: 200,
      json: async () => ({ registrations: [], pagination: { page: 2, page_size: 20, total: 21, total_pages: 2 } }),
    }
  }

  const response = await listMyRegistrations({ page: 2, pageSize: 20 })

  assert.equal(url, '/api/v1/registrations/me?page=2&page_size=20')
  assert.equal(options.credentials, 'include')
  assert.deepEqual(response.pagination, { page: 2, page_size: 20, total: 21, total_pages: 2 })
})
