/** Verify registration view state follows backend results and action outcomes. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { initialRegistrationState, registrationReducer } from '../../src/state/registrationReducer.js'

/** Restore registration state from active, cancelled, and absent API records. */
test('initial and refreshed registration states use the persisted backend status', () => {
  const checking = registrationReducer(initialRegistrationState, {
    type: 'check/start',
    eventKey: '42:5',
  })
  const active = registrationReducer(checking, {
    type: 'check/complete',
    registration: { status: 'registered' },
  })
  const cancelled = registrationReducer(active, {
    type: 'check/complete',
    registration: { status: 'cancelled' },
  })
  const absent = registrationReducer(cancelled, { type: 'check/complete', registration: null })

  assert.deepEqual(active, { eventKey: '42:5', status: 'idle', registered: true, error: null })
  assert.deepEqual(cancelled, { eventKey: '42:5', status: 'idle', registered: false, error: null })
  assert.deepEqual(absent, { eventKey: '42:5', status: 'idle', registered: false, error: null })
})

/** Switch the state used by the enrollment action after successful writes. */
test('successful registration and cancellation immediately switch the available action', () => {
  const pending = registrationReducer(initialRegistrationState, { type: 'register/start' })
  const registered = registrationReducer(pending, { type: 'register/success' })
  const cancelling = registrationReducer(registered, { type: 'cancel/start' })
  const cancelled = registrationReducer(cancelling, { type: 'cancel/success' })

  assert.equal(pending.status, 'loading')
  assert.equal(pending.registered, false)
  assert.equal(registered.registered, true)
  assert.equal(cancelling.registered, true)
  assert.deepEqual(cancelled, { eventKey: null, status: 'cancelled', registered: false, error: null })
})

/** Keep confirmed enrollment state after API failures instead of faking success. */
test('failed API actions preserve the actual prior registration state', () => {
  const failure = new Error('network failure')
  const active = registrationReducer(initialRegistrationState, {
    type: 'check/complete',
    registration: { status: 'registered' },
  })
  const registerError = registrationReducer(active, { type: 'register/failure', error: failure })
  const cancelError = registrationReducer(active, { type: 'cancel/failure', error: failure })
  const lookupError = registrationReducer(active, { type: 'check/failure', error: failure })

  assert.deepEqual(registerError, { eventKey: null, status: 'error', registered: false, error: failure })
  assert.deepEqual(cancelError, { eventKey: null, status: 'error', registered: true, error: failure })
  assert.equal(lookupError.status, 'check-error')
  assert.equal(lookupError.registered, false)
})

/** Ignore a delayed response after navigation has selected another event. */
test('a delayed registration response cannot change the next event state', () => {
  const previousEvent = registrationReducer(initialRegistrationState, {
    type: 'check/start',
    eventKey: '42:5',
  })
  const nextEvent = registrationReducer(previousEvent, {
    type: 'check/start',
    eventKey: '43:5',
  })
  const staleSuccess = registrationReducer(nextEvent, {
    type: 'register/success',
    eventKey: '42:5',
  })

  assert.equal(staleSuccess.eventKey, '43:5')
  assert.equal(staleSuccess.registered, false)
  assert.equal(staleSuccess.status, 'checking')
})
