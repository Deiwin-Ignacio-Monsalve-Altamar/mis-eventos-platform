/** Verify event deletion cannot proceed when its confirmation is declined. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { confirmAndDeleteEvent } from '../../src/utils/eventDeletion.js'

test('declining the event deletion confirmation leaves API state untouched', async () => {
  let confirmationMessage
  let deleteCalls = 0
  const result = await confirmAndDeleteEvent({
    eventTitle: 'Community gathering',
    confirmAction: (message) => {
      confirmationMessage = message
      return false
    },
    deleteAction: async () => { deleteCalls += 1 },
  })

  assert.equal(result, false)
  assert.equal(deleteCalls, 0)
  assert.match(confirmationMessage, /Community gathering/)
  assert.match(confirmationMessage, /no se puede deshacer/)
})

test('confirming event deletion calls the API action exactly once', async () => {
  let deleteCalls = 0
  const result = await confirmAndDeleteEvent({
    eventTitle: 'Community gathering',
    confirmAction: () => true,
    deleteAction: async () => { deleteCalls += 1 },
  })

  assert.equal(result, true)
  assert.equal(deleteCalls, 1)
})
