/** Test API request configuration and normalized HTTP/network failures. */

import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { ApiError, request } from '../../src/api/client.js'

const originalFetch = globalThis.fetch

/** Restore the global fetch implementation after each isolated request test. */
function restoreFetch() {
  globalThis.fetch = originalFetch
}

afterEach(restoreFetch)

test('request sends JSON and includes the backend authentication cookie', async () => {
  let requestUrl
  let requestOptions
  globalThis.fetch = async (url, options) => {
    requestUrl = url
    requestOptions = options
    return { ok: true, status: 200, json: async () => ({ user: { id: 7 } }) }
  }

  const response = await request('/auth/login', {
    method: 'POST',
    body: { email: 'person@example.test', password: 'test-password' },
  })

  assert.equal(requestUrl, '/api/v1/auth/login')
  assert.equal(requestOptions.credentials, 'include')
  assert.equal(requestOptions.headers['Content-Type'], 'application/json')
  assert.deepEqual(JSON.parse(requestOptions.body), {
    email: 'person@example.test',
    password: 'test-password',
  })
  assert.deepEqual(response, { user: { id: 7 } })
})

test('request maps API conflicts to an ApiError with the current version', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 409,
    json: async () => ({
      error: {
        code: 'concurrency_conflict',
        message: 'The event has changed.',
        current_version: 4,
      },
    }),
  })

  await assert.rejects(
    request('/events/12', { method: 'PATCH', body: { version: 3 } }),
    (error) => {
      assert.ok(error instanceof ApiError)
      assert.equal(error.status, 409)
      assert.equal(error.code, 'concurrency_conflict')
      assert.equal(error.currentVersion, 4)
      assert.equal(error.message, 'The event has changed.')
      return true
    },
  )
})

test('request normalizes network failures without exposing transport details', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('private transport detail')
  }

  await assert.rejects(request('/events'), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, null)
    assert.equal(error.code, 'network_error')
    assert.equal(error.message, 'The server could not be reached.')
    return true
  })
})
