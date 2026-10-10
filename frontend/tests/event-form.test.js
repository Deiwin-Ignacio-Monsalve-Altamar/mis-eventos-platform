/** Verify event form validation matches the backend's event input contract. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { toLocalDateTimeValue, validateEventForm } from '../src/utils/eventForm.js'

const validValues = {
  title: '  Community gathering  ',
  description: '  A useful event  ',
  location: '  Bogotá  ',
  starts_at: '2030-01-02T10:00',
  ends_at: '2030-01-02T12:00',
  capacity: '35',
  status: 'published',
}

test('event form trims text and creates the timezone-aware backend payload', () => {
  const result = validateEventForm(validValues)
  assert.deepEqual(result.errors, {})
  assert.deepEqual(result.payload, {
    title: 'Community gathering',
    description: 'A useful event',
    location: 'Bogotá',
    starts_at: new Date(validValues.starts_at).toISOString(),
    ends_at: new Date(validValues.ends_at).toISOString(),
    capacity: 35,
    status: 'published',
  })
})

test('event form rejects invalid title, dates, capacity, location, and status', () => {
  const result = validateEventForm({
    ...validValues,
    title: '   ',
    starts_at: 'not-a-date',
    ends_at: '2030-01-02T12:00',
    capacity: '0.5',
    location: 'L'.repeat(256),
    status: 'archived',
  })

  assert.equal(result.payload, null)
  assert.ok(result.errors.title)
  assert.ok(result.errors.starts_at)
  assert.ok(result.errors.capacity)
  assert.ok(result.errors.location)
  assert.ok(result.errors.status)
})

test('event form rejects an end date earlier than the start date', () => {
  const result = validateEventForm({
    ...validValues,
    starts_at: '2030-01-02T10:00',
    ends_at: '2030-01-02T09:00',
  })

  assert.equal(result.payload, null)
  assert.ok(result.errors.ends_at)
})

test('event form accepts optional empty description and location', () => {
  const result = validateEventForm({ ...validValues, description: '', location: '' })
  assert.equal(result.payload.description, null)
  assert.equal(result.payload.location, null)
})

test('edit datetime values are converted to the browser local input format', () => {
  const date = new Date('2030-01-02T10:05:00Z')
  const pad = (value) => String(value).padStart(2, '0')
  const expected = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
  assert.equal(toLocalDateTimeValue('2030-01-02T10:05:00Z'), expected)
  assert.equal(toLocalDateTimeValue('invalid'), '')
})
