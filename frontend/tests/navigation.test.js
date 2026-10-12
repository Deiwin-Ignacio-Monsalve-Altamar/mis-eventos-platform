/** Verify shared navigation options match the authenticated role and real routes. */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getNavigation, getWorkspaceNavigation, getWorkspaceRole } from '../src/navigation.js'

const validRoutes = new Set([
  '/events',
  '/events/new',
  '/my-events',
  '/my-registrations',
  '/profile',
  '/admin/dashboard',
  '/admin/users',
  '/login',
  '/register',
])

const linksTo = (auth) => {
  const { primaryLinks, accountLinks } = getNavigation(auth)
  return [...primaryLinks, ...accountLinks]
}

test('visitor navigation contains only public discovery and authentication routes', () => {
  const links = linksTo({ status: 'anonymous', user: null })
  assert.deepEqual(links.map(({ to }) => to), ['/events', '/login', '/register'])
})

test('attendee navigation includes registrations and profile without organizer tools', () => {
  const links = linksTo({ status: 'authenticated', user: { role: 'ATTENDEE' } })
  assert.deepEqual(links.map(({ to }) => to), ['/events', '/my-registrations', '/profile'])
})

test('organizer navigation includes event creation, owned events, and profile', () => {
  const links = linksTo({ status: 'authenticated', user: { role: 'ORGANIZER' } })
  assert.deepEqual(links.map(({ to }) => to), ['/events', '/events/new', '/my-events', '/profile'])
})

test('administrator navigation includes available event management and global administration', () => {
  const links = linksTo({ status: 'authenticated', user: { role: 'ADMIN' } })
  assert.deepEqual(links.map(({ to }) => to), [
    '/events', '/events/new', '/my-events', '/admin/dashboard', '/admin/users', '/profile',
  ])
})

test('navigation destinations are implemented and are not duplicated for any role', () => {
  for (const auth of [
    { status: 'anonymous', user: null },
    ...['ATTENDEE', 'ORGANIZER', 'ADMIN'].map((role) => ({ status: 'authenticated', user: { role } })),
  ]) {
    const destinations = linksTo(auth).map(({ to }) => to)
    assert.equal(new Set(destinations).size, destinations.length)
    assert.ok(destinations.every((destination) => validRoutes.has(destination)))
  }
})

test('workspace navigation contains only existing role-appropriate management routes', () => {
  for (const role of ['ADMIN', 'ORGANIZER']) {
    const groups = getWorkspaceNavigation(role)
    const destinations = groups.flatMap(({ links }) => links.map(({ to }) => to))
    assert.equal(new Set(destinations).size, destinations.length)
    assert.ok(destinations.every((destination) => validRoutes.has(destination)))
  }
  assert.deepEqual(getWorkspaceNavigation('ATTENDEE'), [])
})

test('workspace shell is selected only for authenticated administrative and organizer routes', () => {
  const authenticated = (role) => ({ status: 'authenticated', user: { role } })
  assert.equal(getWorkspaceRole(authenticated('ADMIN'), '/admin/dashboard'), 'ADMIN')
  assert.equal(getWorkspaceRole(authenticated('ADMIN'), '/events/42'), 'ADMIN')
  assert.equal(getWorkspaceRole(authenticated('ORGANIZER'), '/my-events'), 'ORGANIZER')
  assert.equal(getWorkspaceRole(authenticated('ORGANIZER'), '/events/42'), 'ORGANIZER')
  assert.equal(getWorkspaceRole(authenticated('ATTENDEE'), '/profile'), null)
  assert.equal(getWorkspaceRole({ status: 'loading' }, '/my-events'), null)
  assert.equal(getWorkspaceRole({ status: 'anonymous' }, '/admin/users'), null)
})
