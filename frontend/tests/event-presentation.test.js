/** Verify data formatting and availability labels stay tied to real API values. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getSessionAvailability, isEventOpenForRegistration, sortSessions } from '../src/utils/eventPresentation.js'

test('session availability presents available, full, pending, and unknown without guessing', () => {
  assert.deepEqual(getSessionAvailability({ available: 2, capacity: 5 }, false, 5), {
    label: 'Disponible',
    detail: '2 cupos disponibles de 5',
    tone: 'available',
  })
  assert.deepEqual(getSessionAvailability({ available: 0, capacity: 5 }, false, 5), {
    label: 'Sin cupos',
    detail: '0 cupos disponibles de 5',
    tone: 'full',
  })
  assert.equal(getSessionAvailability(null, false, 5).tone, 'pending')
  assert.deepEqual(getSessionAvailability(null, true, 5), {
    label: 'Disponibilidad desconocida',
    detail: 'Capacidad máxima: 5',
    tone: 'unknown',
  })
})

test('event availability reflects only published future events', () => {
  const futureTimestamp = '2030-01-10T09:00:00+00:00'
  assert.equal(isEventOpenForRegistration({ status: 'published', starts_at: futureTimestamp }, Date.parse('2029-12-01')), true)
  assert.equal(isEventOpenForRegistration({ status: 'draft', starts_at: futureTimestamp }, Date.parse('2029-12-01')), false)
  assert.equal(isEventOpenForRegistration({ status: 'published', starts_at: 'invalid' }, Date.parse('2029-12-01')), false)
})

test('sessions sort by start time with a stable identifier tie-break', () => {
  const sessions = [
    { id: 3, starts_at: '2030-01-10T10:00:00Z' },
    { id: 2, starts_at: '2030-01-10T09:00:00Z' },
    { id: 1, starts_at: '2030-01-10T09:00:00Z' },
  ]
  assert.deepEqual(sortSessions(sessions).map((session) => session.id), [1, 2, 3])
  assert.deepEqual(sessions.map((session) => session.id), [3, 2, 1])
})
