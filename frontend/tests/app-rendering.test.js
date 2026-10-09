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
    const routes = [
      ['/events', 'Eventos'],
      ['/events/42', 'Select an event to see its details.'],
      ['/events/new', 'Checking your sign-in status…'],
      ['/login', '¡Qué bueno verte!'],
      ['/register', 'Crea tu cuenta'],
      ['/profile', 'Estamos cargando tu perfil…'],
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
    }
  } finally {
    await vite.close()
  }
})
