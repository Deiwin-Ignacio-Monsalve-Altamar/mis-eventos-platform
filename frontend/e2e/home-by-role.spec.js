/** Verify root navigation waits for the backend-authenticated account role. */

import { expect, test } from '@playwright/test'

const userForRole = (role) => ({
  id: 12,
  email: `${role.toLowerCase()}@example.test`,
  first_name: 'Alex',
  last_name: 'Rivera',
  role,
})

/** Mock the existing session and page APIs without a database or external services. */
async function mockApi(page, { role = null, requests = [] } = {}) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    requests.push({ path, method: request.method() })

    if (path === '/auth/me') {
      if (!role) {
        await route.fulfill({ status: 401, json: { error: { code: 'authentication_required' } } })
      } else {
        await route.fulfill({ json: { user: userForRole(role) } })
      }
      return
    }
    if (path === '/events') {
      await route.fulfill({ json: { events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 } } })
      return
    }
    if (path === '/events/mine') {
      await route.fulfill({ json: { events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 } } })
      return
    }
    if (path === '/admin/dashboard') {
      await route.fulfill({ json: { dashboard: {
        summary: {
          users: { total: 0, role_counts: { ATTENDEE: 0, ORGANIZER: 0, ADMIN: 0 } },
          events: { total: 0, upcoming: 0, active: 0, finished: 0, status_counts: { draft: 0, published: 0, cancelled: 0, completed: 0 } },
          registrations: { total: 0, active: 0, cancelled: 0 },
        },
        event_creation_by_month: [],
        registration_activity_by_month: [],
        organizer_activity: [],
      } } })
      return
    }
    if (path === '/admin/users') {
      await route.fulfill({ json: { users: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } } })
      return
    }
    await route.fulfill({ status: 404, json: { error: { code: 'not_found', message: `Unexpected API call: ${path}` } } })
  })
}

test('anonymous root shows the existing login and public routes remain directly accessible', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')

  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: '¡Qué bueno verte!' })).toBeVisible()
  await expect(page.getByLabel('Correo electrónico')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Crear una cuenta' })).toHaveAttribute('href', '/register')

  await page.goto('/events')
  await expect(page.getByRole('heading', { name: 'Planes con otra energía' })).toBeVisible()
  await expect(page).toHaveURL('/events')
})

test('authenticated attendee root redirects to the public event catalogue', async ({ page }) => {
  await mockApi(page, { role: 'ATTENDEE' })
  await page.goto('/')

  await expect(page).toHaveURL('/events')
  await expect(page.getByRole('heading', { name: 'Planes con otra energía' })).toBeVisible()
})

test('authenticated organizer root redirects to their event management page', async ({ page }) => {
  await mockApi(page, { role: 'ORGANIZER' })
  await page.goto('/')

  await expect(page).toHaveURL('/my-events')
  await expect(page.getByRole('heading', { name: 'Mis eventos' })).toBeVisible()
})

test('authenticated administrator root redirects to the protected dashboard', async ({ page }) => {
  await mockApi(page, { role: 'ADMIN' })
  await page.goto('/')

  await expect(page).toHaveURL('/admin/dashboard')
  await expect(page.getByRole('heading', { name: 'Actividad de la plataforma' })).toBeVisible()
})

test('root waits for session resolution before selecting a destination', async ({ page }) => {
  let releaseSession
  const sessionResponse = new Promise((resolve) => { releaseSession = resolve })
  await page.route('**/api/v1/auth/me', async (route) => {
    await sessionResponse
    await route.fulfill({ json: { user: userForRole('ATTENDEE') } })
  })

  await page.goto('/')
  await expect(page.getByText('Estamos verificando tu sesión…')).toBeVisible()
  await expect(page).toHaveURL('/')

  releaseSession()
  await expect(page).toHaveURL('/events')
})

test('login and registration URLs stay available and admin URLs reject an attendee', async ({ page }) => {
  const requests = []
  await mockApi(page, { role: 'ATTENDEE', requests })

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '¡Qué bueno verte!' })).toBeVisible()
  await page.goto('/register')
  await expect(page.getByRole('heading', { name: 'Crea tu cuenta' })).toBeVisible()

  await page.goto('/admin/dashboard')
  await expect(page.getByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  expect(requests.some(({ path }) => path === '/admin/dashboard')).toBe(false)

  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  expect(requests.some(({ path }) => path === '/admin/users')).toBe(false)
})

test('login from root returns through role resolution to the organizer home', async ({ page }) => {
  let role = null
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/api/v1', '')
    if (path === '/auth/me') {
      if (role) return route.fulfill({ json: { user: userForRole(role) } })
      return route.fulfill({ status: 401, json: { error: { code: 'authentication_required' } } })
    }
    if (path === '/auth/login') {
      role = 'ORGANIZER'
      return route.fulfill({ json: { user: userForRole(role) } })
    }
    if (path === '/events/mine') return route.fulfill({ json: { events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 } } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found' } } })
  })

  await page.goto('/')
  await page.getByLabel('Correo electrónico').fill('organizer@example.test')
  await page.getByLabel('Contraseña').fill('example-password')
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL('/my-events')
  await expect(page.getByRole('heading', { name: 'Mis eventos' })).toBeVisible()
})
