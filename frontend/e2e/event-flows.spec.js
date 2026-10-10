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
async function mockApi(page, { authenticated = false, owner = false, failRegistration = false } = {}) {
  let sessions = [{ ...startingSession }]
  let currentEvent = { ...event }

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
        ? { user: { id: 12, email: 'owner@example.test', first_name: 'Alex', last_name: 'Rivera' } }
        : { error: { code: 'unauthorized', message: 'Authentication required.' } }
    } else if (path === '/events/4' && method === 'GET') {
      body = { event: currentEvent }
    } else if (path === '/events/4/capacity' && method === 'GET') {
      body = { capacity: 20, occupied: 1, available: 19 }
    } else if (path === '/events/4/sessions' && method === 'GET') {
      body = { sessions }
    } else if (path === '/events/mine/4' && method === 'GET') {
      status = owner ? 200 : 403
      body = owner
        ? { event: currentEvent }
        : { error: { code: 'forbidden', message: 'Caller is not the event creator.' } }
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
      currentEvent = { ...currentEvent, ...request.postDataJSON(), version: currentEvent.version + 1 }
      body = { event: currentEvent }
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
  await mockApi(page, { authenticated: true })
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
