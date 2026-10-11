/** Verify role-labelled profiles consume their respective API data. */

import { expect, test } from '@playwright/test'

const future = '2030-06-10T14:00:00Z'

async function installProfileApi(page, role) {
  const user = { id: 7, email: 'alex@example.test', first_name: 'Alex', last_name: 'Rivera', role }
  await page.route('**/api/v1/**', async (route) => {
    const { pathname } = new URL(route.request().url())
    const path = pathname.replace('/api/v1', '')
    if (path === '/auth/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user }) })
    if (path === '/admin/dashboard') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ dashboard: {
      summary: {
        users: { total: 12, role_counts: { ATTENDEE: 8, ORGANIZER: 3, ADMIN: 1 } },
        events: { total: 6, status_counts: { draft: 1, published: 3, cancelled: 1, completed: 1 }, upcoming: 2, active: 1, finished: 2 },
        registrations: { total: 18, active: 14, cancelled: 4 },
      },
      event_creation_by_month: [{ month: '2030-01', count: 1 }, { month: '2030-02', count: 0 }],
      registration_activity_by_month: [{ month: '2030-01', count: 3 }, { month: '2030-02', count: 2 }],
      organizer_activity: [{ user_id: 9, name: 'Morgan Organizer', event_count: 2, active_registrations: 6 }],
    } }) })
    if (path === '/events/mine/metrics') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      summary: { total_events: 2, upcoming_events: 1, active_events: 1, finished_events: 0, cancelled_events: 0, active_registrations: 7, status_counts: { draft: 1, published: 1, cancelled: 0, completed: 0 } },
      events: [{ id: 25, title: 'Own Conference', description: 'Only owned event data.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 10, status: 'published', version: 1, active_registrations: 4, session_count: 2, available_seats: 6 }],
    }) })
    if (path === '/registrations/me/summary') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: { total: 1, active: 1, upcoming: 1, past: 0, cancelled: 0 } }) })
    if (path === '/registrations/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ registrations: [{ id: 3, status: 'registered', registered_at: future, event: { id: 25, title: 'Attending Conference', description: 'Your registered event.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 10, status: 'published' } }], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } }) })
    if (path === '/events/recommendations/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ recommendations: Array.from({ length: 5 }, (_, index) => ({ event: { id: 40 + index, title: `Available Event ${index + 1}`, description: 'An upcoming community event.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 20, status: 'published' }, available_seats: 20 - index })) }) })
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: `Unexpected ${path}` } }) })
  })
}

test('administrator profile shows role totals, trends, and organizer activity', async ({ page }) => {
  await installProfileApi(page, 'ADMIN')
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Actividad de la plataforma' })).toBeVisible()
  await expect(page.getByText('Usuarios', { exact: true })).toBeVisible()
  await expect(page.getByText('Morgan Organizer')).toBeVisible()
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByText('Administrador')).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Administrar usuarios' })).toBeVisible()
})

test('organizer profile presents owned event capacity, sessions, and activity', async ({ page }) => {
  await installProfileApi(page, 'ORGANIZER')
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Resumen de gestión' })).toBeVisible()
  await expect(page.getByText('Inscripciones activas', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Own Conference' })).toBeVisible()
  await expect(page.getByText('2 sesiones')).toBeVisible()
  await expect(page.getByText('6 cupos libres')).toBeVisible()
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByText('Organizador')).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Administrar usuarios' })).toHaveCount(0)
})

test('attendee profile keeps registrations and navigable available-event recommendations', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Mis inscripciones' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Attending Conference' })).toBeVisible()
  const rail = page.getByRole('list', { name: 'Recomendaciones de eventos' })
  await expect(rail).toBeVisible()
  await expect(rail.getByRole('link', { name: 'Available Event 1' })).toHaveAttribute('href', '/events/40')
  await page.getByRole('button', { name: 'Ver eventos siguientes' }).click()
  await expect.poll(() => rail.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByText('Asistente')).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Administrar usuarios' })).toHaveCount(0)
})
