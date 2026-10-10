/** Verify logout clears authenticated identity and private application caches. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'vite'

/** Load the application reducer through Vite's JSX-aware test environment. */
async function loadReducer() {
  const vite = await createServer({
    appType: 'custom',
    configFile: 'vite.config.js',
    server: { hmr: false, middlewareMode: true, ws: false },
  })
  const module = await vite.ssrLoadModule('/src/state/appReducer.js')
  return { reducer: module.appReducer, close: () => vite.close() }
}

test('confirmed logout clears authentication and cached account data', async () => {
  const { reducer, close } = await loadReducer()
  try {
    const state = {
      auth: { user: { id: 7, email: 'owner@example.test' }, status: 'authenticated', error: null },
      events: { items: [{ id: 9 }], status: 'success' },
      selectedEvent: { event: { id: 9 }, status: 'success', sessions: [{ id: 1 }] },
      eventCreation: { status: 'success', error: null },
      eventMutation: { status: 'success', error: null },
    }

    const loggedOut = reducer(state, { type: 'auth/logout-success' })

    assert.deepEqual(loggedOut.auth, { user: null, status: 'anonymous', error: null })
    assert.deepEqual(loggedOut.events.items, [])
    assert.equal(loggedOut.selectedEvent.event, null)
    assert.notEqual(loggedOut, state)
  } finally {
    await close()
  }
})
