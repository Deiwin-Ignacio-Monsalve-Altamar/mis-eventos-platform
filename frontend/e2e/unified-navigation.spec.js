/** Verify role-aware navigation and the accessible mobile navigation control. */

import { expect, test } from '@playwright/test'

const implementedRoutes = [
  '/events', '/events/new', '/my-events', '/my-registrations', '/profile',
  '/admin/dashboard', '/admin/users', '/login', '/register',
]

async function mockApi(page, role = null) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    if (path === '/auth/me') {
      if (!role) {
        await route.fulfill({ status: 401, json: { error: { code: 'authentication_required' } } })
      } else {
        await route.fulfill({ json: { user: {
          id: 5,
          email: `${role.toLowerCase()}@example.test`,
          first_name: 'Alex',
          last_name: 'Rivera',
          role,
        } } })
      }
      return
    }
    if (path === '/events') {
      await route.fulfill({ json: { events: [], pagination: { page: 1, page_size: 9, total: 0, total_pages: 0 } } })
      return
    }
    await route.fulfill({ status: 404, json: { error: { code: 'not_found' } } })
  })
}

async function expectNoUnknownRoutes(page) {
  const hrefs = await page.getByRole('navigation', { name: 'Navegación principal' })
    .locator('a')
    .evaluateAll((links) => links.map((link) => link.getAttribute('href')))
  expect(hrefs.every((href) => implementedRoutes.includes(href))).toBe(true)
  expect(new Set(hrefs).size).toBe(hrefs.length)
}

test('visitor sees only the public catalogue, login, and registration navigation', async ({ page }) => {
  await mockApi(page)
  await page.goto('/events')

  const navigation = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(navigation.getByRole('link', { name: 'Eventos' })).toBeVisible()
  await expect(navigation.getByRole('link', { name: 'Iniciar sesión' })).toHaveAttribute('href', '/login')
  await expect(navigation.getByRole('link', { name: 'Registrarse' })).toHaveAttribute('href', '/register')
  await expect(navigation.getByRole('link', { name: 'Crear evento' })).toHaveCount(0)
  await expectNoUnknownRoutes(page)
})

test('attendee sees registration navigation and profile in the account menu', async ({ page }) => {
  await mockApi(page, 'ATTENDEE')
  await page.goto('/events')

  const navigation = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(navigation.getByRole('link', { name: 'Mis inscripciones' })).toHaveAttribute('href', '/my-registrations')
  await expect(navigation.getByRole('link', { name: 'Crear evento' })).toHaveCount(0)
  await expect(navigation.getByRole('link', { name: 'Mis eventos' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  await expect(page.getByRole('navigation', { name: 'Menú de usuario' }).getByRole('link', { name: 'Perfil' })).toHaveAttribute('href', '/profile')
  await expectNoUnknownRoutes(page)
})

test('organizer sees event creation and owned event management destinations', async ({ page }) => {
  await mockApi(page, 'ORGANIZER')
  await page.goto('/events')

  const navigation = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(navigation.getByRole('link', { name: 'Crear evento' })).toHaveAttribute('href', '/events/new')
  await expect(navigation.getByRole('link', { name: 'Mis eventos' })).toHaveAttribute('href', '/my-events')
  await expect(navigation.getByRole('link', { name: 'Mis inscripciones' })).toHaveCount(0)
  await expectNoUnknownRoutes(page)
})

test('administrator sees event tools and global dashboard and user administration', async ({ page }) => {
  await mockApi(page, 'ADMIN')
  await page.goto('/events')

  const navigation = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(navigation.getByRole('link', { name: 'Panel administrativo' })).toHaveAttribute('href', '/admin/dashboard')
  await expect(navigation.getByRole('link', { name: 'Usuarios' })).toHaveAttribute('href', '/admin/users')
  await expect(navigation.getByRole('link', { name: 'Mis eventos' })).toHaveAttribute('href', '/my-events')
  await page.getByRole('button', { name: 'Abrir menú de usuario' }).click()
  await expect(page.getByRole('navigation', { name: 'Menú de usuario' }).getByRole('link', { name: 'Usuarios' })).toHaveCount(0)
  await expectNoUnknownRoutes(page)
})

test('mobile navigation opens, closes with Escape, and closes after choosing a destination', async ({ page }) => {
  await mockApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/events')

  const toggle = page.locator('.mobile-nav-toggle')
  const navigation = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(navigation).toBeHidden()
  await expect(toggle).toHaveAttribute('aria-label', 'Abrir navegación')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(toggle).toHaveAttribute('aria-label', 'Cerrar navegación')
  await expect(navigation.getByRole('link', { name: 'Eventos' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(toggle).toBeFocused()
  await expect(navigation).toBeHidden()

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-label', 'Cerrar navegación')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-label', 'Abrir navegación')
  await expect(navigation).toBeHidden()

  await toggle.click()
  await navigation.getByRole('link', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toHaveCount(0)
})
