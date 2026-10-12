/** Verify role-labelled profiles consume their respective API data. */

import { expect, test } from '@playwright/test'

const future = '2030-06-10T14:00:00Z'

async function installProfileApi(page, role, sessionResponse = {}, {
  loginRequired = false,
  adminDashboardResponse,
  ownerMetricsResponse,
  recommendationResponse,
} = {}) {
  const user = { id: 7, email: 'alex@example.test', first_name: 'Alex', last_name: 'Rivera', role }
  let authenticated = !loginRequired
  await page.route('**/api/v1/**', async (route) => {
    const { pathname } = new URL(route.request().url())
    const path = pathname.replace('/api/v1', '')
    if (path === '/auth/me') {
      return authenticated
        ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user }) })
        : route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { code: 'authentication_required' } }) })
    }
    if (path === '/auth/login' && route.request().method() === 'POST') {
      authenticated = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user }) })
    }
    if (path === '/admin/dashboard') {
      const payload = adminDashboardResponse?.payload || { dashboard: {
        summary: {
          users: { total: 12, role_counts: { ATTENDEE: 8, ORGANIZER: 3, ADMIN: 1 } },
          events: { total: 6, status_counts: { draft: 1, published: 3, cancelled: 1, completed: 1 }, upcoming: 2, active: 1, finished: 2 },
          registrations: { total: 18, active: 14, cancelled: 4 },
        },
        event_creation_by_month: [{ month: '2030-01', count: 1 }, { month: '2030-02', count: 0 }],
        registration_activity_by_month: [{ month: '2030-01', count: 3 }, { month: '2030-02', count: 2 }],
        organizer_activity: [{ user_id: 9, name: 'Morgan Organizer', event_count: 2, active_registrations: 6 }],
      } }
      return route.fulfill({ status: adminDashboardResponse?.status || 200, contentType: 'application/json', body: JSON.stringify(payload) })
    }
    if (path === '/events/mine/metrics') {
      const payload = ownerMetricsResponse?.payload || {
        summary: { total_events: 2, upcoming_events: 1, active_events: 1, finished_events: 0, cancelled_events: 0, active_registrations: 7, status_counts: { draft: 1, published: 1, cancelled: 0, completed: 0 } },
        events: [{ id: 25, title: 'Own Conference', description: 'Only owned event data.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 10, status: 'published', version: 1, active_registrations: 4, session_count: 2, available_seats: 6 }],
      }
      return route.fulfill({ status: ownerMetricsResponse?.status || 200, contentType: 'application/json', body: JSON.stringify(payload) })
    }
    if (path === '/events/mine') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 } }) })
    if (path === '/registrations/me/summary') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: { total: 1, active: 1, upcoming: 1, past: 0, cancelled: 0 } }) })
    if (path === '/registrations/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ registrations: [{ id: 3, status: 'registered', registered_at: future, event: { id: 25, title: 'Attending Conference', description: 'Your registered event.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 10, status: 'published' } }], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } }) })
    if (path === '/session-registrations/me') {
      if (sessionResponse.delayMs) await new Promise((resolve) => setTimeout(resolve, sessionResponse.delayMs))
      return route.fulfill({
        status: sessionResponse.status || 200,
        contentType: 'application/json',
        body: JSON.stringify(sessionResponse.payload || {
          registrations: [
            { id: 8, status: 'active', registered_at: future, event: { id: 25, title: 'Attending Conference', status: 'published', location: 'Bogotá' }, session: { id: 12, title: 'Opening session', description: 'Welcome and overview.', starts_at: future, ends_at: '2030-06-10T15:00:00Z', capacity: 10 } },
            { id: 9, status: 'cancelled', registered_at: future, event: { id: 25, title: 'Attending Conference', status: 'published', location: 'Bogotá' }, session: { id: 13, title: 'Workshop', description: null, starts_at: '2030-06-10T16:00:00Z', ends_at: '2030-06-10T17:00:00Z', capacity: 10 } },
          ],
          pagination: { page: 1, page_size: 20, total: 2, total_pages: 1 },
        }),
      })
    }
    if (path === '/events/recommendations/me') {
      const payload = recommendationResponse?.payload || { recommendations: Array.from({ length: 5 }, (_, index) => ({ event: { id: 40 + index, title: `Available Event ${index + 1}`, description: 'An upcoming community event.', location: 'Bogotá', starts_at: future, ends_at: '2030-06-10T18:00:00Z', capacity: 20, status: 'published' }, available_seats: 20 - index })) }
      return route.fulfill({ status: recommendationResponse?.status || 200, contentType: 'application/json', body: JSON.stringify(payload) })
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: `Unexpected ${path}` } }) })
  })
}

test('administrator workspace separates global navigation and keeps dashboard data real', async ({ page }) => {
  await installProfileApi(page, 'ADMIN')
  await page.goto('/admin/dashboard')
  const sidebar = page.getByRole('navigation', { name: 'Navegación del espacio de trabajo' })
  await expect(sidebar.getByRole('link', { name: 'Vista general' })).toHaveAttribute('href', '/admin/dashboard')
  await expect(sidebar.getByRole('link', { name: 'Usuarios y roles' })).toHaveAttribute('href', '/admin/users')
  await expect(sidebar.getByRole('link', { name: 'Mis eventos' })).toHaveAttribute('href', '/my-events')
  await expect(page.getByRole('heading', { name: 'Actividad de la plataforma' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toHaveCount(0)
})

test('organizer workspace has a mobile drawer and keeps event operations in its own shell', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installProfileApi(page, 'ORGANIZER')
  await page.goto('/profile')
  const toggle = page.locator('.workspace-menu-toggle')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  const sidebar = page.getByRole('navigation', { name: 'Navegación del espacio de trabajo' })
  await expect(sidebar.getByRole('link', { name: 'Resumen' })).toHaveAttribute('href', '/profile')
  await sidebar.getByRole('link', { name: 'Mis eventos' }).click()
  await expect(page).toHaveURL('/my-events')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('heading', { name: 'Mis eventos' })).toBeVisible()
})

for (const { role, profileHeading } of [
  { role: 'ATTENDEE', profileHeading: 'Mis inscripciones' },
  { role: 'ORGANIZER', profileHeading: 'Resumen de gestión' },
  { role: 'ADMIN', profileHeading: 'Actividad de la plataforma' },
]) {
  test(`${role.toLowerCase()} login from /login opens the role's profile`, async ({ page }) => {
    await installProfileApi(page, role, {}, { loginRequired: true })
    await page.goto('/login')
    await page.getByLabel('Correo electrónico').fill('alex@example.test')
    await page.getByLabel('Contraseña').fill('example-password')
    await page.getByRole('button', { name: 'Iniciar sesión' }).click()

    await expect(page).toHaveURL('/profile')
    await expect(page.getByRole('heading', { name: profileHeading, exact: true })).toBeVisible()
  })
}

test('administrator profile shows role totals, trends, and organizer activity', async ({ page }) => {
  await installProfileApi(page, 'ADMIN')
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Actividad de la plataforma' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Navegación del espacio de trabajo' }).getByRole('link', { name: 'Usuarios y roles' })).toBeVisible()
  await expect(page.getByRole('article').getByText('Morgan Organizer')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Eventos por organizador' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Inscripciones activas por organizador' })).toBeVisible()
  const workspace = page.locator('.workspace-sidebar')
  await expect(workspace.getByText('Administración global')).toBeVisible()
  await expect(page.getByText('Sesión activa')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
})

test('organizer profile presents owned event capacity, sessions, and activity', async ({ page }) => {
  await installProfileApi(page, 'ORGANIZER')
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Resumen de gestión' })).toBeVisible()
  await expect(page.getByText('Inscripciones activas', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Own Conference' })).toBeVisible()
  await expect(page.getByText('2 sesiones')).toBeVisible()
  await expect(page.getByText('6 cupos libres')).toBeVisible()
  const workspace = page.locator('.workspace-sidebar')
  await expect(workspace.getByText('Espacio de organización')).toBeVisible()
  await expect(page.getByText('Sesión activa')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
})

test('attendee profile shows event and session registrations with available-event recommendations', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Mis inscripciones', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Attending Conference' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Mis inscripciones a sesiones' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Opening session' })).toBeVisible()
  await expect(page.getByText('Inscripción activa')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Workshop' })).toBeVisible()
  await expect(page.getByText('Inscripción cancelada')).toBeVisible()
  const rail = page.getByRole('list', { name: 'Recomendaciones de eventos' })
  await expect(rail).toBeVisible()
  await expect(rail.getByRole('link', { name: 'Available Event 1' })).toHaveAttribute('href', '/events/40')
  await page.getByRole('button', { name: 'Ver eventos siguientes' }).click()
  await expect.poll(() => rail.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  const menu = page.getByRole('navigation', { name: 'Menú de usuario' })
  await expect(menu.getByText('Asistente')).toBeVisible()
  await expect(menu.getByText('Sesión activa')).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Administrar usuarios' })).toHaveCount(0)
})

test('attendee profile displays session registration loading state', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE', { delayMs: 500 })
  await page.goto('/profile')
  await expect(page.getByText('Cargando tus sesiones…')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Opening session' })).toBeVisible()
})

test('attendee profile displays an empty session registration state', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE', {
    payload: { registrations: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } },
  })
  await page.goto('/profile')
  await expect(page.getByText('Aún no tienes inscripciones a sesiones.')).toBeVisible()
})

test('attendee profile displays session registration errors and retry action', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE', {
    status: 503,
    payload: { error: { code: 'service_unavailable', message: 'Unavailable.' } },
  })
  await page.goto('/profile')
  await expect(page.getByRole('alert').getByText('Unavailable.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Intentar de nuevo' })).toBeVisible()
})

test('administrator profile displays empty and failed dashboard states', async ({ page }) => {
  await installProfileApi(page, 'ADMIN', {}, {
    adminDashboardResponse: { payload: { dashboard: {
      summary: {
        users: { total: 0, role_counts: { ATTENDEE: 0, ORGANIZER: 0, ADMIN: 0 } },
        events: { total: 0, status_counts: { draft: 0, published: 0, cancelled: 0, completed: 0 }, upcoming: 0, active: 0, finished: 0 },
        registrations: { total: 0, active: 0, cancelled: 0 },
      },
      event_creation_by_month: [],
      registration_activity_by_month: [],
      organizer_activity: [],
    } } },
  })
  await page.goto('/profile')
  await expect(page.getByText('Aún no hay actividad registrada para mostrar.')).toBeVisible()

  await page.unrouteAll()
  await installProfileApi(page, 'ADMIN', {}, {
    adminDashboardResponse: { status: 503, payload: { error: { code: 'service_unavailable', message: 'Unavailable.' } } },
  })
  await page.goto('/profile')
  await expect(page.getByRole('alert').getByText('Unavailable.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Intentar de nuevo' })).toBeVisible()
})

test('organizer profile displays empty and failed owner-metrics states', async ({ page }) => {
  await installProfileApi(page, 'ORGANIZER', {}, {
    ownerMetricsResponse: { payload: {
      summary: { total_events: 0, upcoming_events: 0, active_events: 0, finished_events: 0, cancelled_events: 0, active_registrations: 0, status_counts: { draft: 0, published: 0, cancelled: 0, completed: 0 } },
      events: [],
    } },
  })
  await page.goto('/profile')
  await expect(page.getByText('Aún no has creado eventos.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Crear tu primer evento' })).toHaveAttribute('href', '/events/new')

  await page.unrouteAll()
  await installProfileApi(page, 'ORGANIZER', {}, {
    ownerMetricsResponse: { status: 503, payload: { error: { code: 'service_unavailable', message: 'Unavailable.' } } },
  })
  await page.goto('/profile')
  await expect(page.getByRole('alert').getByText('Unavailable.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Intentar de nuevo' })).toBeVisible()
})

test('attendee recommendations display empty and failed states', async ({ page }) => {
  await installProfileApi(page, 'ATTENDEE', {}, {
    recommendationResponse: { payload: { recommendations: [] } },
  })
  await page.goto('/profile')
  await expect(page.getByText('Por ahora no encontramos eventos próximos con cupos disponibles.')).toBeVisible()

  await page.unrouteAll()
  await installProfileApi(page, 'ATTENDEE', {}, {
    recommendationResponse: { status: 503, payload: { error: { code: 'service_unavailable', message: 'Unavailable.' } } },
  })
  await page.goto('/profile')
  await expect(page.getByRole('alert').getByText('Unavailable.')).toBeVisible()
})
