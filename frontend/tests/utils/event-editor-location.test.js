/** Verify editor query updates preserve unrelated event navigation state. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getEventEditorLocation } from '../../src/utils/eventEditorLocation.js'

test('opening and closing the event editor changes only its query flag', () => {
  assert.equal(getEventEditorLocation('/events/4', '?page=2&edit=0', true), '/events/4?page=2&edit=1')
  assert.equal(getEventEditorLocation('/events/4', '?page=2&edit=1', false), '/events/4?page=2')
  assert.equal(getEventEditorLocation('/events/4', '', false), '/events/4')
})
