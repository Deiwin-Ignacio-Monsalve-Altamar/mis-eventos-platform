/** Verify event CRUD reducer transitions keep catalogue and detail data coherent. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'vite'

const originalEvent = {
  id: 42,
  title: 'Community gathering',
  description: 'Meet the community.',
  location: 'Bogotá',
  starts_at: '2030-01-02T10:00:00Z',
  ends_at: '2030-01-02T12:00:00Z',
  capacity: 35,
  status: 'published',
  version: 1,
}

/** Load the real reducer through the configured Vite JSX/module environment. */
async function loadReducer() {
  const vite = await createServer({
    appType: 'custom',
    configFile: 'vite.config.js',
    server: { hmr: false, middlewareMode: true, ws: false },
  })
  const module = await vite.ssrLoadModule('/src/state/appReducer.js')
  return { reducer: module.appReducer, close: () => vite.close() }
}

/** Build the event-related state shape used by the application reducer. */
function stateWithEvent() {
  return {
    events: {
      items: [originalEvent],
      pagination: { page: 1, page_size: 9, total: 1, total_pages: 1 },
      query: '',
      page: 1,
      status: 'success',
      error: null,
    },
    selectedEvent: {
      event: originalEvent,
      status: 'success',
      error: null,
      sessions: [],
      sessionsStatus: 'success',
      sessionsError: null,
    },
    eventCreation: { status: 'idle', error: null },
    eventMutation: { status: 'idle', error: null },
  }
}

test('successful event edits update the catalogue card and open detail state', async () => {
  const { reducer, close } = await loadReducer()
  try {
    const updatedEvent = { ...originalEvent, title: 'Updated gathering', version: 2 }
    const state = reducer(stateWithEvent(), { type: 'event-updating/success', event: updatedEvent })
    assert.equal(state.events.items[0].title, 'Updated gathering')
    assert.equal(state.selectedEvent.event.title, 'Updated gathering')
    assert.equal(state.eventMutation.status, 'success')
  } finally {
    await close()
  }
})

test('successful deletion removes the catalogue item and clears the selected detail', async () => {
  const { reducer, close } = await loadReducer()
  try {
    const state = reducer(stateWithEvent(), { type: 'event-deleting/success', eventId: 42 })
    assert.deepEqual(state.events.items, [])
    assert.equal(state.events.pagination.total, 0)
    assert.equal(state.events.pagination.total_pages, 0)
    assert.equal(state.selectedEvent.event, null)
    assert.equal(state.selectedEvent.error.code, 'not_found')
    assert.equal(state.eventMutation.status, 'success')
  } finally {
    await close()
  }
})

test('event creation inserts the real response into cached catalogue and detail state', async () => {
  const { reducer, close } = await loadReducer()
  try {
    const createdEvent = { ...originalEvent, id: 43, title: 'New gathering' }
    const state = reducer(stateWithEvent(), { type: 'event-creation/success', event: createdEvent })
    assert.deepEqual(state.events.items.map((item) => item.id), [42, 43])
    assert.equal(state.events.pagination.total, 2)
    assert.equal(state.selectedEvent.event.id, 43)
  } finally {
    await close()
  }
})
