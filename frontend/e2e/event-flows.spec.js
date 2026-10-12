/** Cover public event access, registration, and owner event/session management. */

import { expect, test } from '@playwright/test'

const event = {
  id: 4,
  title: 'Community Design Day',
  description: 'A practical design gathering.',
  location: 'Central Hall',
  starts_at: '2027-06-10T14:00:00Z',
  ends_at: '2027-06-10T20:00:00Z',
  capacity: 20,
  status: 'published',
  version: 1,
}

const startingSession = {
  id: 9,
  event_id: 4,
  title: 'Opening talk',
  description: 'Welcome and introductions.',
  starts_at: event.starts_at,
  ends_at: '2027-06-10T15:00:00Z',
  capacity: 20,
  version: 1,
  speaker_ids: [],
}

/** Install API routes for a repeatable anonymous, attendee, or owner scenario. */
async function mockApi(page, {
  authenticated = false,
  owner = false,
  role = null,
  draft = false,
  initialStatus = null,
  failPublish = false,
  publishDelayMs = 0,
  privateEventError = null,
  privateEventDelayMs = 0,
  failRegistration = false,
  failLogout = false,
} = {}) {
  let sessions = [{ ...startingSession }]
  let currentEvent = { ...event, status: initialStatus || (draft ? 'draft' : event.status), images: [{ url: 'https://images.example.test/cover.webp', position: 0 }] }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const method = request.method()
    let status = 200
    let body = {}

    if (path === '/auth/me' && method === 'GET') {
      status = authenticated ? 200 : 401
      body = authenticated
        ? { user: { id: 12, email: 'owner@example.test', first_name: 'Alex', last_name: 'Rivera', role: role || (owner ? 'ORGANIZER' : 'ATTENDEE') } }
        : { error: { code: 'unauthorized', message: 'Authentication required.' } }
    } else if (path === '/auth/login' && method === 'POST') {
      body = { user: { id: 12, email: 'owner@example.test', first_name: 'Alex', last_name: 'Rivera', role: role || (owner ? 'ORGANIZER' : 'ATTENDEE') } }
    } else if (path === '/auth/logout' && method === 'POST') {
      status = failLogout ? 500 : 200
      body = failLogout
        ? { error: { code: 'server_error', message: 'Logout could not be completed.' } }
        : { message: 'Logged out.' }
    } else if (path === '/events' && method === 'POST') {
      currentEvent = { ...request.postDataJSON(), id: 11, version: 1 }
      status = 201
      body = { event: currentEvent }
    } else if (path === '/events/mine' && method === 'GET') {
      body = { events: [currentEvent], pagination: { page: 1, page_size: 9, total: 1, total_pages: 1 } }
    } else if ((path === '/events/4' || path === '/events/11') && method === 'GET') {
      status = currentEvent.status === 'published' ? 200 : 404
      body = status === 200 ? { event: currentEvent } : { error: { code: 'not_found', message: 'Not found.' } }
    } else if ((path === '/events/4/capacity' || path === '/events/11/capacity') && method === 'GET') {
      body = { capacity: 20, occupied: 1, available: 19 }
    } else if ((path === '/events/4/sessions' || path === '/events/11/sessions') && method === 'GET') {
      body = { sessions }
    } else if (/^\/events\/mine\/\d+$/.test(path) && method === 'GET') {
      if (privateEventError === 'network') {
        await route.abort()
        return
      }
      const eventId = Number(path.split('/').at(-1))
      const canAccessPrivateEvent = owner || (currentEvent.id !== 4 && currentEvent.id === eventId)
      status = privateEventError || (canAccessPrivateEvent ? 200 : 404)
      body = owner
        ? { event: currentEvent }
        : canAccessPrivateEvent
          ? { event: currentEvent }
          : { error: { code: privateEventError ? 'server_error' : 'not_found', message: 'Private event lookup failed.' } }
    } else if (path === '/registrations/me' && method === 'GET') {
      body = { registrations: [], pagination: { page: 1, total_pages: 1, total: 0 } }
    } else if (path === '/events/4/registrations/me' && method === 'POST') {
      status = failRegistration ? 409 : 201
      body = failRegistration
        ? { error: { code: 'capacity_exceeded', message: 'This event has no available places.' } }
        : { message: 'Registration created.' }
    } else if (path.match(/^\/events\/4\/sessions\/\d+\/capacity$/) && method === 'GET') {
      body = { capacity: 20, occupied: 1, available: 19 }
    } else if (path === '/events/4' && method === 'PATCH') {
      const changes = request.postDataJSON()
      if (changes.status === 'published' && failPublish) {
        status = 422
        body = { error: { code: 'validation_error', message: 'Capacity cannot be lower than active event registrations.' } }
      } else {
        if (changes.status === 'published' && publishDelayMs) {
          await new Promise((resolve) => setTimeout(resolve, publishDelayMs))
        }
        currentEvent = { ...currentEvent, ...changes, version: currentEvent.version + 1 }
        body = { event: currentEvent }
      }
    } else if (path === '/events/4/sessions' && method === 'POST') {
      const data = request.postDataJSON()
      const created = { ...data, id: 10, event_id: 4, version: 1, speaker_ids: [] }
      sessions = [...sessions, created]
      status = 201
      body = { session: created }
    } else if (path.match(/^\/events\/4\/sessions\/\d+$/) && method === 'PATCH') {
      const sessionId = Number(path.split('/').at(-1))
      const data = request.postDataJSON()
      sessions = sessions.map((item) => item.id === sessionId ? { ...item, ...data, version: item.version + 1 } : item)
      body = { session: sessions.find((item) => item.id === sessionId) }
    } else if (path.match(/^\/events\/4\/sessions\/\d+$/) && method === 'DELETE') {
      const sessionId = Number(path.split('/').at(-1))
      sessions = sessions.filter((item) => item.id !== sessionId)
      status = 204
    } else {
      status = 404
      body = { error: { code: 'not_found', message: `Unexpected test request: ${method} ${path}` } }
    }

    if (/^\/events\/mine\/\d+$/.test(path) && privateEventDelayMs) {
      await new Promise((resolve) => setTimeout(resolve, privateEventDelayMs))
    }
    await route.fulfill({ status, contentType: 'application/json', body: status === 204 ? '' : JSON.stringify(body) })
  })
}

test('shows event details and directs anonymous attendees to sign in', async ({ page }) => {
  await mockApi(page)
  await page.goto('/events/4')

  await expect(page.getByRole('heading', { name: event.title })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Inscribirme' })).toBeVisible()
  await page.getByRole('button', { name: 'Inscribirme' }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test('guests see sign-in and account actions instead of the event form', async ({ page }) => {
  await mockApi(page)
  await page.goto('/events/new')

  await expect(page.getByRole('heading', { name: 'Inicia sesión para crear un evento' })).toBeVisible()
  const accessPanel = page.getByRole('region', { name: 'Inicia sesión para crear un evento' })
  await expect(accessPanel.getByRole('link', { name: 'Iniciar sesión' })).toHaveAttribute('href', '/login')
  await expect(accessPanel.getByRole('link', { name: 'Crear una cuenta' })).toHaveAttribute('href', '/register')
  await expect(page.getByRole('button', { name: 'Crear evento' })).toHaveCount(0)

  await accessPanel.getByRole('link', { name: 'Crear una cuenta' }).click()
  await expect(page).toHaveURL(/\/register$/)
})

test('sign-in from event creation returns to the authenticated creation form', async ({ page }) => {
  await mockApi(page)
  await page.goto('/events/new')
  await page.getByRole('region', { name: 'Inicia sesión para crear un evento' }).getByRole('link', { name: 'Iniciar sesión' }).click()
  await page.getByLabel('Correo electrónico').fill('owner@example.test')
  await page.getByLabel('Contraseña').fill('example-password')
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()

  await expect(page).toHaveURL(/\/events\/new$/)
  await expect(page.getByRole('button', { name: 'Crear evento' })).toBeVisible()
})

test('authenticated users can create an event', async ({ page }) => {
  await mockApi(page, { authenticated: true, role: 'ORGANIZER' })
  await page.goto('/events/new')
  await page.getByLabel('Nombre del evento').fill('My new event')
  await page.getByLabel('Fecha y hora de inicio').fill('2030-06-10T14:00')
  await page.getByLabel('Fecha y hora de finalización').fill('2030-06-10T16:00')
  await page.getByLabel('Capacidad').fill('25')
  await page.getByRole('button', { name: 'Crear evento' }).click()

  await expect(page).toHaveURL(/\/events\/11$/)
  await expect(page.getByRole('heading', { name: 'My new event' })).toBeVisible()
})

test('avatar menu opens, navigates to profile, and has no footer logout duplicate', async ({ page }) => {
  await mockApi(page, { authenticated: true })
  await page.goto('/events')
  const avatar = page.getByRole('button', { name: 'Abrir menú de usuario' })
  await avatar.click()

  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByRole('link', { name: 'Perfil' })).toBeVisible()
  await menu.getByRole('link', { name: 'Perfil' }).click()
  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.locator('.site-footer').getByRole('button', { name: 'Cerrar sesión' })).toHaveCount(0)
})

test('settings stay disabled, Escape closes the menu, and outside clicks dismiss it', async ({ page }) => {
  await mockApi(page, { authenticated: true })
  await page.goto('/events')
  const avatar = page.getByRole('button', { name: 'Abrir menú de usuario' })
  await avatar.click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByRole('button', { name: /Ajustes.*Próximamente/ })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)
  await expect(avatar).toBeFocused()

  await avatar.click()
  await page.getByRole('banner').getByRole('link', { name: 'Mis Eventos, explorar eventos' }).click()
  await expect(menu).toHaveCount(0)
  await expect(page).toHaveURL(/\/events$/)
})

test('attendee logout clears the session, redirects to events, and fits a mobile viewport', async ({ page }) => {
  await mockApi(page, { authenticated: true })
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/events')
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  const logoutButton = menu.getByRole('button', { name: 'Cerrar sesión' })
  await expect(logoutButton).toBeVisible()
  const menuBounds = await menu.boundingBox()
  expect(menuBounds.x).toBeGreaterThanOrEqual(0)
  expect(menuBounds.x + menuBounds.width).toBeLessThanOrEqual(375)
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth)
  await logoutButton.click()

  await expect(page).toHaveURL(/\/events$/)
  await expect(page.getByRole('button', { name: 'Abrir menú de usuario' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Abrir navegación' }).click()
  await expect(page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Iniciar sesión' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Abrir menú de usuario' })).toHaveCount(0)
})

for (const role of ['ORGANIZER', 'ADMIN']) {
  test(`${role.toLowerCase()} logout clears the session and redirects to login`, async ({ page }) => {
    await mockApi(page, { authenticated: true, role })
    await page.goto('/events')
    await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
    await page.getByRole('navigation', { name: 'Menú de usuario' }).getByRole('button', { name: 'Cerrar sesión' }).click()

    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Bienvenido de nuevo' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Abrir menú de usuario' })).toHaveCount(0)
  })
}

test('failed logout keeps the user authenticated and shows an error', async ({ page }) => {
  await mockApi(page, { authenticated: true, failLogout: true })
  await page.goto('/events')
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  await page.getByRole('navigation', { name: 'Menú de usuario' }).getByRole('button', { name: 'Cerrar sesión' }).click()

  await expect(page.getByText('Logout could not be completed.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abrir menú de usuario' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Menú de usuario' }).getByRole('button', { name: 'Cerrar sesión' })).toBeEnabled()
})

test('keeps registration available and explains an API rejection', async ({ page }) => {
  await mockApi(page, { authenticated: true, failRegistration: true })
  await page.goto('/events/4')

  await page.getByRole('button', { name: 'Inscribirme' }).click()
  await expect(page.getByText('Ya no quedan cupos disponibles para este evento.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Inscribirme' })).toBeVisible()
})

test('switches to cancellation after a successful registration', async ({ page }) => {
  await mockApi(page, { authenticated: true })
  await page.goto('/events/4')

  await page.getByRole('button', { name: 'Inscribirme' }).click()
  await expect(page.getByRole('button', { name: 'Cancelar inscripción' })).toBeVisible()
})

test('does not show owner controls when the owner check is denied', async ({ page }) => {
  await mockApi(page, { authenticated: true, role: 'ORGANIZER' })
  await page.goto('/events/4')

  await expect(page.getByRole('button', { name: 'Editar evento' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Agregar sesión' })).toHaveCount(0)
})

test('opens the event editor from the query and saves changes', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true })
  await page.goto('/events/4')

  await page.getByRole('button', { name: 'Editar evento' }).click()
  await expect(page).toHaveURL(/\?edit=1$/)
  await expect(page.getByRole('dialog', { name: 'Editar evento' })).toBeVisible()
  await page.getByLabel('Nombre del evento').fill('Updated Design Day')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()

  await expect(page.getByRole('heading', { name: 'Updated Design Day' })).toBeVisible()
  await expect(page).not.toHaveURL(/\?edit=1$/)
})

test('opens and edits an own draft through the private event endpoint without replacing its images', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true, role: 'ORGANIZER', draft: true })
  await page.route('https://images.example.test/**', (route) => route.fulfill({
    status: 200,
    contentType: 'image/gif',
    body: Buffer.from('R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=', 'base64'),
  }))
  const publicDetailRequests = []
  const draftSessionRequests = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname.endsWith('/events/4')) publicDetailRequests.push(request.url())
    if (url.pathname.endsWith('/events/4/sessions')) draftSessionRequests.push(request.url())
  })
  await page.goto('/my-events')
  await page.getByRole('link', { name: 'Community Design Day' }).click()

  await expect(page).toHaveURL(/\/events\/4$/)
  await expect(page.getByRole('heading', { name: event.title })).toBeVisible()
  await expect(page.getByText('Borrador', { exact: true })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'La agenda se podrá consultar y administrar cuando el evento esté publicado.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Agregar sesión' })).toHaveCount(0)
  await expect(page.getByRole('img', { name: /Community Design Day/ }).first()).toHaveAttribute('src', 'https://images.example.test/cover.webp')
  await page.getByRole('button', { name: 'Editar evento' }).click()
  await expect(page.getByLabel('Nombre del evento')).toHaveValue(event.title)
  await expect(page.locator('[aria-label^="Galería actual"]')).toBeVisible()
  await page.getByLabel('Nombre del evento').fill('Updated draft')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()

  await expect(page.getByRole('heading', { name: 'Updated draft' })).toBeVisible()
  await expect(page.locator('img.event-cover').first()).toHaveAttribute('src', 'https://images.example.test/cover.webp')
  expect(publicDetailRequests).toHaveLength(0)
  expect(draftSessionRequests).toHaveLength(0)
})

test('saves and publishes an own draft, then refreshes the organizer event list', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true, role: 'ORGANIZER', draft: true, publishDelayMs: 500 })
  const publishRequests = []
  page.on('request', (request) => {
    if (request.method() === 'PATCH' && new URL(request.url()).pathname === '/api/v1/events/4') {
      publishRequests.push(request.postDataJSON())
    }
  })
  await page.goto('/events/4')
  await page.getByRole('button', { name: 'Editar evento' }).click()
  await page.getByLabel('Nombre del evento').fill('Published Design Day')
  await page.getByRole('button', { name: 'Publicar evento' }).dblclick()

  await expect(page).toHaveURL(/\/my-events$/)
  const publishedRow = page.getByRole('row', { name: /Published Design Day/ })
  await expect(publishedRow.getByText('Publicado')).toBeVisible()
  expect(publishRequests).toHaveLength(1)
  expect(publishRequests[0]).toMatchObject({ title: 'Published Design Day', status: 'published', version: 1 })
})

test('shows backend publication validation and preserves the draft form values', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true, role: 'ORGANIZER', draft: true, failPublish: true })
  await page.goto('/events/4')
  await page.getByRole('button', { name: 'Editar evento' }).click()
  await page.getByLabel('Nombre del evento').fill('Draft with changes')
  await page.getByRole('button', { name: 'Publicar evento' }).click()

  await expect(page.getByText('El servidor rechazó los cambios: Capacity cannot be lower than active event registrations.')).toBeVisible()
  await expect(page.getByText('Capacity cannot be lower than active event registrations.', { exact: true })).toBeVisible()
  await expect(page.locator('.event-form #event-capacity')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByLabel('Nombre del evento')).toHaveValue('Draft with changes')
  await expect(page.getByLabel('Estado')).toHaveValue('draft')
  await expect(page.getByRole('button', { name: 'Publicar evento' })).toBeEnabled()
  await expect(page).toHaveURL(/\?edit=1$/)
})

for (const status of ['published', 'cancelled', 'completed']) {
  test(`does not offer draft publication for a ${status} event`, async ({ page }) => {
    await mockApi(page, { authenticated: true, owner: true, role: 'ORGANIZER', initialStatus: status })
    await page.goto('/events/4')
    await page.getByRole('button', { name: 'Editar evento' }).click()

    await expect(page.getByRole('button', { name: 'Publicar evento' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeVisible()
  })
}

test('does not fall back to public detail when the private owner lookup fails', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: false, role: 'ORGANIZER', draft: true })
  await page.goto('/events/4')

  await expect(page.getByText('No encontramos este evento. Puede que ya no esté disponible.')).toBeVisible()
  await expect(page.getByRole('heading', { name: event.title })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Editar evento' })).toHaveCount(0)
})

test('keeps server lookup errors distinct from a missing draft', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: false, role: 'ORGANIZER', draft: true, privateEventError: 503 })
  await page.goto('/events/4')

  await expect(page.getByRole('alert').filter({ hasText: 'Ocurrió un problema al cargar la información.' })).toBeVisible()
  await expect(page.getByRole('heading', { name: event.title })).toHaveCount(0)
})

test('shows a loading state while the private draft lookup is pending', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true, role: 'ORGANIZER', draft: true, privateEventDelayMs: 700 })
  await page.goto('/events/4')

  await expect(page.getByText('Estamos cargando el evento…')).toBeVisible()
  await expect(page.getByRole('heading', { name: event.title })).toBeVisible()
})

test('keeps a private lookup network error separate from event not found', async ({ page }) => {
  await mockApi(page, { authenticated: true, role: 'ORGANIZER', draft: true, privateEventError: 'network' })
  await page.goto('/events/4')

  await expect(page.getByText('No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
  await expect(page.getByText('No encontramos este evento. Puede que ya no esté disponible.')).toHaveCount(0)
})

test('allows the owner to add, edit, and delete a session', async ({ page }) => {
  await mockApi(page, { authenticated: true, owner: true })
  await page.goto('/events/4')
  await expect(page.getByRole('heading', { name: startingSession.title })).toBeVisible()

  await page.getByRole('button', { name: 'Agregar sesión' }).click()
  await page.getByLabel('Nombre de la sesión').fill('New workshop')
  await page.getByRole('button', { name: 'Agregar sesión' }).last().click()
  await expect(page.getByRole('heading', { name: 'New workshop' })).toBeVisible()

  const sessionCard = page.locator('.session-item').filter({ has: page.getByRole('heading', { name: 'New workshop' }) })
  await sessionCard.getByRole('button', { name: 'Editar sesión' }).click()
  await page.getByLabel('Nombre de la sesión').fill('Updated workshop')
  await page.getByRole('button', { name: 'Guardar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Updated workshop' })).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  const updatedCard = page.locator('.session-item').filter({ has: page.getByRole('heading', { name: 'Updated workshop' }) })
  await updatedCard.getByRole('button', { name: 'Eliminar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Updated workshop' })).toHaveCount(0)
})

test('keeps the event page within a narrow mobile viewport', async ({ page }) => {
  await mockApi(page)
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/events/4')

  await expect(page.getByRole('heading', { name: event.title })).toBeVisible()
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth)
})
