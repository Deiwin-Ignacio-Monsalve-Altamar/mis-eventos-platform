/** Verify authentication form validation against the backend contract. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { validateLogin, validateRegistration } from '../src/pages/authValidation.js'

/** Build valid registration values that a focused assertion can override. */
function validRegistration(overrides = {}) {
  return {
    first_name: 'Ari',
    last_name: 'Rivera',
    email: 'ari@example.test',
    password: 'long-enough-password',
    ...overrides,
  }
}

test('registration accepts valid trimmed values and backend boundary lengths', () => {
  assert.equal(validateRegistration(validRegistration({ first_name: ' A ' })), null)
  assert.equal(validateRegistration(validRegistration({ first_name: 'x'.repeat(100) })), null)
  assert.equal(validateRegistration(validRegistration({ last_name: 'x'.repeat(100) })), null)
  assert.equal(validateRegistration(validRegistration({ email: `${'a'.repeat(306)}@b.co` })), null)
  assert.equal(validateRegistration(validRegistration({ password: '12345678' })), null)
  assert.equal(validateRegistration(validRegistration({ password: 'x'.repeat(128) })), null)
})

test('registration rejects invalid names, email, and password lengths', () => {
  assert.equal(validateRegistration(validRegistration({ first_name: '  ' })).field, 'first_name')
  assert.equal(validateRegistration(validRegistration({ first_name: 'x'.repeat(101) })).field, 'first_name')
  assert.equal(validateRegistration(validRegistration({ last_name: '' })).field, 'last_name')
  assert.equal(validateRegistration(validRegistration({ email: 'not-an-email' })).field, 'email')
  assert.equal(validateRegistration(validRegistration({ email: `${'a'.repeat(310)}@example.test` })).field, 'email')
  assert.equal(validateRegistration(validRegistration({ password: 'short' })).field, 'password')
  assert.equal(validateRegistration(validRegistration({ password: 'x'.repeat(129) })).field, 'password')
})

test('login requires a valid email and non-empty password', () => {
  assert.equal(validateLogin({ email: ' person@example.test ', password: 'secret' }), null)
  assert.equal(validateLogin({ email: 'invalid', password: 'secret' }).field, 'email')
  assert.equal(validateLogin({ email: 'person@example.test', password: '' }).field, 'password')
})
