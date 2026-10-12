/** Guard application context wiring and the required route rendering. */

import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { test } from 'node:test'
import { createServer } from 'vite'

test('application provider renders every required route without a blank screen', async () => {
  const vite = await createServer({
    appType: 'custom',
    configFile: 'vite.config.js',
    server: { hmr: false, middlewareMode: true, ws: false },
  })

  try {
    const { default: App } = await vite.ssrLoadModule('/src/App.jsx')
    const { default: AppHeader } = await vite.ssrLoadModule('/src/components/AppHeader.jsx')
    const routes = [
      ['/', 'Estamos verificando tu sesión…'],
      ['/events', 'Eventos'],
      ['/events/42', 'Estamos cargando el evento…'],
      ['/events/new', 'Estamos verificando tu sesión…'],
      ['/login', 'Bienvenido de nuevo'],
      ['/register', 'Crea tu cuenta'],
      ['/profile', 'Estamos verificando tu sesión…'],
      ['/my-events', 'Estamos verificando tu sesión…'],
      ['/my-registrations', 'Estamos verificando tu sesión…'],
      ['/admin/dashboard', 'Estamos verificando tu sesión…'],
      ['/admin/users', 'Estamos verificando tu sesión…'],
      ['/route-that-does-not-exist', 'Página no encontrada'],
    ]

    for (const [location, expectedContent] of routes) {
      const html = renderToString(
        createElement(
          StaticRouter,
          { location },
          createElement(App),
        ),
      )
      assert.ok(html.includes(expectedContent), `Route ${location} did not render.`)
      if (location === '/') {
        assert.ok(html.includes('aria-label="Verificación de sesión"'), 'The root route must wait for authentication.')
        assert.ok(!html.includes('site-header'), 'The root entry must not flash public navigation while authentication loads.')
        assert.ok(!html.includes('site-footer'), 'The root entry must not flash the public footer while authentication loads.')
      }
      if (location === '/login' || location === '/register') {
        assert.ok(!html.includes('site-footer'), 'Authentication pages must not render the shared footer.')
      }
    }

    const authenticatedHeader = renderToString(
      createElement(
        StaticRouter,
        { location: '/events' },
        createElement(AppHeader, {
          auth: { status: 'authenticated', user: { id: 1, role: 'ORGANIZER' } },
        }),
      ),
    )
    assert.ok(authenticatedHeader.includes('aria-label="Abrir menú de usuario"'), 'Authenticated users must have a user avatar menu.')
    assert.ok(!authenticatedHeader.includes('Mi perfil'), 'The header must not render a text-based profile button.')
    assert.ok(authenticatedHeader.includes('href="/my-events"'), 'Authenticated users must have a link to their events.')
    assert.ok(!authenticatedHeader.includes('Únete gratis'), 'Authenticated users must not see the registration CTA.')
  } finally {
    await vite.close()
  }
})
