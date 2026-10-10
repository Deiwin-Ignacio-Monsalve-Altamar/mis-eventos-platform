/** Verify event management forms and controls render only for signed-in users. */

import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'
import { Route, Routes, StaticRouter } from 'react-router-dom'
import { test } from 'node:test'
import { createServer } from 'vite'

const event = {
  id: 42,
  title: 'Community gathering',
  description: 'Meet the community.',
  location: 'Bogotá',
  starts_at: '2030-01-02T10:00:00Z',
  ends_at: '2030-01-02T12:00:00Z',
  capacity: 35,
  status: 'published',
  version: 3,
}

/** Create the repository's existing Vite SSR harness for component checks. */
async function createTestServer() {
  return createServer({
    appType: 'custom',
    configFile: 'vite.config.js',
    server: { hmr: false, middlewareMode: true, ws: false },
  })
}

/** Render a component tree inside the same route and state contexts as the app. */
function renderWithState(component, state, AppStateContext, location = '/events/42') {
  return renderToString(
    createElement(
      StaticRouter,
      { location },
      createElement(AppStateContext.Provider, { value: { state } }, component),
    ),
  )
}

test('unauthenticated users receive a login action instead of event management controls', async () => {
  const vite = await createTestServer()
  try {
    const [{ default: CreateEventPage }, { default: EventDetailsPage }] = await Promise.all([
      vite.ssrLoadModule('/src/pages/CreateEventPage.jsx'),
      vite.ssrLoadModule('/src/pages/EventDetailsPage.jsx'),
    ])
    const { default: AppStateContext } = await vite.ssrLoadModule('/src/state/AppStateContext.js')
    const anonymousState = {
      auth: { status: 'anonymous', user: null, error: null },
      eventCreation: { status: 'idle', error: null },
      selectedEvent: {
        event,
        status: 'success',
        error: null,
        sessions: [],
        sessionsStatus: 'success',
        sessionsError: null,
      },
    }

    const createPage = renderWithState(createElement(CreateEventPage), anonymousState, AppStateContext, '/events/new')
    assert.match(createPage, /Inicia sesión para crear un evento/)
    assert.match(createPage, /href="\/login"/)
    assert.doesNotMatch(createPage, /event-title/)

    const detailPage = renderToString(
      createElement(
        StaticRouter,
        { location: '/events/42' },
        createElement(
          AppStateContext.Provider,
          { value: { state: anonymousState, loadEvent: () => {}, loadEventSessions: () => {} } },
          createElement(Routes, null, createElement(Route, { path: '/events/:eventId', element: createElement(EventDetailsPage) })),
        ),
      ),
    )
    assert.match(detailPage, /Inicia sesión para administrar este evento/)
    assert.doesNotMatch(detailPage, /Editar evento/)
    assert.doesNotMatch(detailPage, /Eliminar evento/)
  } finally {
    await vite.close()
  }
})

test('event details hide management controls until the owner-only endpoint confirms ownership', async () => {
  const vite = await createTestServer()
  try {
    const { default: EventDetailsPage } = await vite.ssrLoadModule('/src/pages/EventDetailsPage.jsx')
    const { default: AppStateContext } = await vite.ssrLoadModule('/src/state/AppStateContext.js')
    const authenticatedState = {
      auth: { status: 'authenticated', user: { id: 5 }, error: null },
      selectedEvent: {
        event,
        status: 'success',
        error: null,
        sessions: [],
        sessionsStatus: 'success',
        sessionsError: null,
      },
    }
    const markup = renderToString(
      createElement(
        StaticRouter,
        { location: '/events/42' },
        createElement(
          AppStateContext.Provider,
          { value: { state: authenticatedState, loadEvent: () => {}, loadEventSessions: () => {} } },
          createElement(Routes, null, createElement(Route, { path: '/events/:eventId', element: createElement(EventDetailsPage) })),
        ),
      ),
    )

    assert.doesNotMatch(markup, /Editar evento/)
    assert.doesNotMatch(markup, /Eliminar evento/)
  } finally {
    await vite.close()
  }
})

test('shared edit form is prefilled with the event returned by the API', async () => {
  const vite = await createTestServer()
  try {
    const { default: EventForm } = await vite.ssrLoadModule('/src/components/EventForm.jsx')
    const { toLocalDateTimeValue } = await vite.ssrLoadModule('/src/utils/eventForm.js')
    const markup = renderToString(createElement(EventForm, {
      event,
      onSubmit: async () => {},
      isSubmitting: false,
    }))

    assert.match(markup, /value="Community gathering"/)
    assert.match(markup, /value="Bogotá"/)
    assert.match(markup, /value="35"/)
    assert.ok(markup.includes(`value="${toLocalDateTimeValue(event.starts_at)}"`))
    assert.match(markup, /value="published" selected/)
    assert.match(markup, /Guardar cambios/)
  } finally {
    await vite.close()
  }
})

test('authenticated profile renders the logout action', async () => {
  const vite = await createTestServer()
  try {
    const { default: ProfilePage } = await vite.ssrLoadModule('/src/pages/ProfilePage.jsx')
    const { default: AppStateContext } = await vite.ssrLoadModule('/src/state/AppStateContext.js')
    const markup = renderToString(
      createElement(
        StaticRouter,
        { location: '/profile' },
        createElement(AppStateContext.Provider, {
          value: {
            state: { auth: { status: 'authenticated', user: { id: 5, first_name: 'Alex', last_name: 'Rivera', email: 'alex@example.test' } } },
            signOut: async () => {},
          },
        }, createElement(ProfilePage)),
      ),
    )

    assert.match(markup, /Cerrar sesión/)
  } finally {
    await vite.close()
  }
})

test('registration success and duplicate responses each render one notice', async () => {
  const vite = await createTestServer()
  try {
    const { default: RegistrationNotice } = await vite.ssrLoadModule('/src/components/RegistrationNotice.jsx')
    const success = renderToString(createElement(RegistrationNotice, {
      registration: { status: 'success', registered: true },
    }))
    const duplicate = renderToString(createElement(RegistrationNotice, {
      registration: { status: 'duplicate', registered: true },
    }))

    assert.equal((success.match(/role="status"/g) || []).length, 1)
    assert.match(success, /Tu inscripción quedó confirmada/)
    assert.equal((duplicate.match(/role="status"/g) || []).length, 1)
    assert.match(duplicate, /Ya tienes una inscripción activa/)
  } finally {
    await vite.close()
  }
})
