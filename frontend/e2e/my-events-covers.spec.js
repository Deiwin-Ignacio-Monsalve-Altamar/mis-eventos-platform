/** Verify organizer event cards select safe cover images and keep their actions. */

import { expect, test } from '@playwright/test'

const events = [
  {
    id: 31,
    title: 'Galería ordenada',
    starts_at: '2030-06-10T14:00:00Z',
    ends_at: '2030-06-10T20:00:00Z',
    capacity: 20,
    version: 1,
    status: 'published',
    images: [
      { url: 'https://images.example.test/secondary.webp', position: 1 },
      { url: 'https://images.example.test/main.webp', position: 0 },
    ],
  },
  {
    id: 32,
    title: 'Sin galería',
    starts_at: '2030-06-11T14:00:00Z',
    ends_at: '2030-06-11T20:00:00Z',
    capacity: 12,
    version: 1,
    status: 'draft',
    images: [],
  },
  {
    id: 33,
    title: 'URL vacía',
    starts_at: '2030-06-12T14:00:00Z',
    ends_at: '2030-06-12T20:00:00Z',
    capacity: 12,
    version: 1,
    status: 'cancelled',
    images: [{ url: '', position: 0 }],
  },
  {
    id: 34,
    title: 'URL inválida',
    starts_at: '2030-06-13T14:00:00Z',
    ends_at: '2030-06-13T20:00:00Z',
    capacity: 12,
    version: 1,
    status: 'completed',
    images: [{ url: 'not a url', position: 0 }],
  },
  {
    id: 35,
    title: 'Fallo al cargar',
    starts_at: '2030-06-14T14:00:00Z',
    ends_at: '2030-06-14T20:00:00Z',
    capacity: 20,
    version: 1,
    status: 'published',
    images: [{ url: 'https://images.example.test/broken.webp', position: 0 }],
  },
  {
    id: 36,
    title: 'Sin posición principal',
    starts_at: '2030-06-15T14:00:00Z',
    ends_at: '2030-06-15T20:00:00Z',
    capacity: 12,
    version: 1,
    status: 'draft',
    images: [{ url: 'https://images.example.test/secondary-only.webp', position: 1 }],
  },
]

async function installDashboardApi(page, { role = 'ORGANIZER', eventsForOwner = [], failFirstList = false, listDelayMs = 0 } = {}) {
  let listCalls = 0
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/api/v1', '')
    if (path === '/auth/me') {
      await route.fulfill({ json: { user: { id: 12, email: 'owner@example.test', role } } })
      return
    }
    if (path === '/events/mine') {
      listCalls += 1
      if (failFirstList && listCalls <= 2) {
        if (listDelayMs) await new Promise((resolve) => setTimeout(resolve, listDelayMs))
        await route.fulfill({ status: 503, json: { error: { code: 'server_error', message: 'The event list is temporarily unavailable.' } } })
        return
      }
      if (listDelayMs) await new Promise((resolve) => setTimeout(resolve, listDelayMs))
      await route.fulfill({ json: { events: eventsForOwner, pagination: { page: 1, page_size: 9, total: eventsForOwner.length, total_pages: 1 } } })
      return
    }
    if (path === '/events/mine/metrics') {
      await route.fulfill({
        json: {
          summary: { total_events: eventsForOwner.length, upcoming_events: 0, active_events: 0, finished_events: 0, cancelled_events: 0, active_registrations: 0 },
          events: [],
        },
      })
      return
    }
    if (path.endsWith('/sessions')) {
      await route.fulfill({ json: { sessions: [] } })
      return
    }
    await route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'Unexpected request.' } } })
  })
}

test('my events use the position-zero cover, branded fallbacks, and existing actions', async ({ page }) => {
  const apiPaths = []
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    apiPaths.push(path)

    if (path === '/auth/me') {
      await route.fulfill({ json: { user: { id: 12, email: 'owner@example.test', role: 'organizer' } } })
      return
    }
    if (path === '/events/mine') {
      const search = url.searchParams.get('q')?.toLocaleLowerCase('es') || ''
      const status = url.searchParams.get('status') || ''
      const filteredEvents = events.filter((event) => (
        (!search || event.title.toLocaleLowerCase('es').includes(search))
        && (!status || event.status === status)
      ))
      await route.fulfill({
        json: {
          events: filteredEvents,
          pagination: { page: 1, page_size: 9, total: filteredEvents.length, total_pages: 1 },
        },
      })
      return
    }
    if (path === '/events/mine/metrics') {
      await route.fulfill({
        json: {
          summary: { total_events: 5, upcoming_events: 3, active_events: 1, finished_events: 1, cancelled_events: 1, active_registrations: 8 },
          events: [
            { ...events[0], session_count: 2, active_registrations: 8, available_seats: 12 },
            { ...events[4], session_count: 0, active_registrations: 0, available_seats: 20 },
          ],
        },
      })
      return
    }
    if (path === '/events/31/sessions') {
      await route.fulfill({
        json: {
          sessions: [
            { id: 1, title: 'Sesión pasada', starts_at: '2025-06-10T14:00:00Z', ends_at: '2025-06-10T15:00:00Z' },
            { id: 2, title: 'Charla principal', starts_at: '2030-06-10T16:00:00Z', ends_at: '2030-06-10T17:00:00Z' },
          ],
        },
      })
      return
    }
    if (path === '/events/35/sessions') {
      await route.fulfill({ json: { sessions: [] } })
      return
    }
    await route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'Unexpected request.' } } })
  })
  await page.route('https://images.example.test/*.webp', (route) => route.fulfill({
    status: 200,
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 2"><rect width="2" height="2" fill="purple"/></svg>',
  }))
  await page.route('https://images.example.test/broken.webp', (route) => route.abort())

  await page.goto('/my-events')

  const orderedCard = page.locator('.organizer-event-row').filter({ hasText: 'Galería ordenada' })
  await expect(orderedCard.locator('img')).toHaveAttribute('src', 'https://images.example.test/main.webp')
  await expect(orderedCard.locator('img')).toHaveAttribute('alt', 'Galería ordenada, portada del evento')
  await expect(orderedCard.getByRole('heading', { name: 'Galería ordenada' })).toBeVisible()
  await expect(orderedCard.locator('.status-badge')).toHaveText('Publicado')
  await expect(orderedCard.getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/events/31?edit=1')
  await expect(orderedCard.getByRole('button', { name: 'Cancelar evento' })).toBeVisible()
  await expect(orderedCard.getByRole('button', { name: 'Eliminar' })).toBeVisible()
  await expect(orderedCard.locator('img')).not.toHaveAttribute('src', /secondary/)
  await expect(orderedCard).toContainText('Próxima: Charla principal')
  await expect(orderedCard).toContainText('2 sesiones')
  await expect(orderedCard).toContainText('8 inscripciones activas')
  await expect(page.getByLabel('Indicadores de tus eventos')).toContainText('Eventos creados')
  await expect(page.getByLabel('Indicadores de tus eventos')).toContainText('5')

  const desktopImage = await orderedCard.locator('img').boundingBox()
  expect(desktopImage.width).toBeGreaterThan(0)
  expect(desktopImage.height).toBeGreaterThan(0)
  expect(desktopImage.width / desktopImage.height).toBeCloseTo(78 / 56, 1)

  for (const title of ['Sin galería', 'URL vacía', 'URL inválida', 'Fallo al cargar', 'Sin posición principal']) {
    const card = page.locator('.organizer-event-row').filter({ hasText: title })
    await expect(card.locator('.event-artwork')).toBeVisible()
    await expect(card.locator('img')).toHaveCount(0)
  }

  const failedCard = page.locator('.organizer-event-row').filter({ hasText: 'Fallo al cargar' })
  await expect(failedCard.locator('.event-artwork')).toHaveText(/Mis Eventos/)
  const statuses = {
    'Galería ordenada': { cancel: true },
    'Sin galería': { cancel: true },
    'URL vacía': { cancel: false },
    'URL inválida': { cancel: false },
    'Fallo al cargar': { cancel: true },
    'Sin posición principal': { cancel: true },
  }
  for (const [title, state] of Object.entries(statuses)) {
    const row = page.locator('.organizer-event-row').filter({ hasText: title })
    await expect(row.getByRole('link', { name: 'Editar' })).toBeVisible()
    await expect(row.getByRole('button', { name: 'Cancelar evento' })).toHaveCount(state.cancel ? 1 : 0)
    await expect(row.getByRole('button', { name: 'Eliminar' })).toBeVisible()
  }

  await page.setViewportSize({ width: 768, height: 900 })
  const tabletDimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }))
  expect(tabletDimensions.documentWidth).toBeLessThanOrEqual(tabletDimensions.viewportWidth)

  await page.setViewportSize({ width: 375, height: 812 })
  await expect(page.locator('.organizer-event-row').first()).toBeVisible()
  const mobileImage = await orderedCard.locator('img').boundingBox()
  expect(mobileImage.width / mobileImage.height).toBeCloseTo(78 / 56, 1)
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth)
  const eventApiPaths = apiPaths.filter((path) => path.startsWith('/events/'))
  expect(eventApiPaths.length).toBeGreaterThan(0)
  expect(eventApiPaths).toContain('/events/mine')
  expect(eventApiPaths).toContain('/events/mine/metrics')
  expect(eventApiPaths.filter((path) => path.endsWith('/sessions')).every((path) => ['/events/31/sessions', '/events/35/sessions'].includes(path))).toBe(true)

  await page.getByLabel('Buscar mis eventos').fill('Galería ordenada')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page.locator('.organizer-event-row')).toHaveCount(1)
  await expect(page.locator('.organizer-event-row')).toContainText('Galería ordenada')
  await page.getByLabel('Estado').selectOption('cancelled')
  await expect(page.getByText('No encontramos eventos con estos criterios.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Limpiar filtros' }).click()
  await expect(page.locator('.organizer-event-row')).toHaveCount(events.length)
})

test('my events keep the list usable through loading and retry after a server error', async ({ page }) => {
  await installDashboardApi(page, { eventsForOwner: [events[1]], failFirstList: true, listDelayMs: 250 })
  await page.goto('/my-events')

  await expect(page.getByText('Cargando tus eventos…')).toBeVisible()
  await expect(page.getByRole('alert').filter({ hasText: 'The event list is temporarily unavailable.' })).toBeVisible()
  await page.getByRole('button', { name: 'Intentar de nuevo' }).click()
  await expect(page.getByRole('heading', { name: 'Sin galería' })).toBeVisible()
})

test('my events show an honest empty state and retain the create route', async ({ page }) => {
  await installDashboardApi(page)
  await page.goto('/my-events')

  await expect(page.getByText('Aún no has creado eventos.')).toBeVisible()
  await expect(page.locator('.organizer-empty').getByRole('link', { name: 'Crear evento' })).toHaveAttribute('href', '/events/new')
  await expect(page.getByLabel('Indicadores de tus eventos')).toContainText('0')
})

test('a role denied by the owner event API cannot see event rows or management actions', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    if (path === '/auth/me') {
      await route.fulfill({ json: { user: { id: 13, email: 'attendee@example.test', role: 'ATTENDEE' } } })
      return
    }
    if (path === '/events/mine' || path === '/events/mine/metrics') {
      await route.fulfill({ status: 403, json: { error: { code: 'forbidden', message: 'Organizer role required.' } } })
      return
    }
    await route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'Unexpected request.' } } })
  })
  await page.goto('/my-events')

  await expect(page.getByRole('alert').filter({ hasText: 'No tienes permiso' }).first()).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(1)
  await expect(page.locator('.organizer-event-row')).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Editar' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Cancelar evento' })).toHaveCount(0)
})
