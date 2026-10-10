/** Verify local browser telemetry filters sensitive values and avoids duplicates. */

import assert from 'node:assert/strict'
import test from 'node:test'

import { request } from '../src/api/client.js'
import {
  initializeFrontendObservability,
  reportApiError,
} from '../src/observability.js'

/** Create a browser-like event target with controllable performance APIs. */
function createWindow() {
  const listeners = new Map()
  return {
    document: { readyState: 'complete' },
    performance: { getEntriesByType: () => [{ duration: 1250 }] },
    addEventListener(name, callback) {
      listeners.set(name, [...(listeners.get(name) || []), callback])
    },
    removeEventListener(name, callback) {
      listeners.set(name, (listeners.get(name) || []).filter((item) => item !== callback))
    },
    dispatch(name, event) {
      for (const callback of listeners.get(name) || []) callback(event)
    },
    listenerCount(name) {
      return (listeners.get(name) || []).length
    },
  }
}

/** Replace console levels while capturing emitted telemetry and restoring afterward. */
function captureConsole() {
  const entries = []
  const original = Object.fromEntries(['debug', 'warn', 'error'].map((level) => [
    level,
    console[level],
  ]))
  for (const level of Object.keys(original)) {
    console[level] = (message) => entries.push({ level, payload: JSON.parse(message) })
  }
  return {
    entries,
    restore() {
      Object.assign(console, original)
    },
  }
}

test('global browser errors and rejections are logged locally without duplicate API errors', () => {
  const window = createWindow()
  const captured = captureConsole()
  const cleanup = initializeFrontendObservability(window)
  const apiError = new Error('private token=do-not-log')

  reportApiError(apiError, 503)
  window.dispatch('error', { message: 'sensitive request data' })
  window.dispatch('unhandledrejection', { reason: apiError })
  window.dispatch('unhandledrejection', { reason: new TypeError('private email@example.test') })

  const events = captured.entries.map(({ payload }) => payload.event)
  const output = JSON.stringify(captured.entries)

  assert.equal(events.filter((name) => name === 'mis_eventos_frontend_api_errors_total').length, 1)
  assert.equal(events.filter((name) => name === 'mis_eventos_frontend_errors_total').length, 2)
  assert.ok(events.includes('mis_eventos_frontend_page_load_duration_seconds'))
  assert.equal(output.includes('do-not-log'), false)
  assert.equal(output.includes('email@example.test'), false)

  cleanup()
  assert.equal(window.listenerCount('error'), 0)
  captured.restore()
})

test('API HTTP and network failures emit bounded error and duration events', async () => {
  const captured = captureConsole()
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({ error: { code: 'unavailable', message: 'secret=hidden' } }),
    })
    await assert.rejects(request('/private/path?email=private@example.test'), { status: 503 })

    globalThis.fetch = async () => {
      throw new TypeError('network failed')
    }
    await assert.rejects(request('/private/path'), { code: 'network_error' })
  } finally {
    globalThis.fetch = originalFetch
    captured.restore()
  }

  const events = captured.entries.map(({ payload }) => payload.event)
  const output = JSON.stringify(captured.entries)
  assert.equal(events.filter((name) => name === 'mis_eventos_frontend_api_errors_total').length, 2)
  assert.equal(events.filter((name) => name === 'mis_eventos_frontend_api_request_duration_seconds').length, 2)
  assert.equal(output.includes('private@example.test'), false)
  assert.equal(output.includes('/private/path'), false)
  assert.equal(output.includes('hidden'), false)
})

test('supported LCP and CLS observations use the frontend web-vital event identifier', () => {
  const captured = captureConsole()
  const observations = []
  class FakePerformanceObserver {
    constructor(callback) {
      this.callback = callback
      observations.push(this)
    }

    observe() {}

    disconnect() {}
  }
  const window = createWindow()
  window.PerformanceObserver = FakePerformanceObserver
  const cleanup = initializeFrontendObservability(window)

  observations[0].callback({ getEntries: () => [{ startTime: 2500 }] })
  observations[1].callback({
    getEntries: () => [
      { value: 0.1, hadRecentInput: false },
      { value: 0.4, hadRecentInput: true },
    ],
  })

  const vitalEvents = captured.entries
    .map(({ payload }) => payload)
    .filter(({ event }) => event === 'mis_eventos_frontend_web_vitals')
  assert.deepEqual(vitalEvents.map(({ metric, value }) => [metric, value]), [
    ['LCP', 2.5],
    ['CLS', 0.1],
  ])

  cleanup()
  captured.restore()
})
