/** Exercise the administrator directory, access guard, search, and promotion flow. */

import { expect, test } from '@playwright/test'

const attendees = [
  { id: 8, email: 'sam@example.test', first_name: 'Sam', last_name: 'Rivera', role: 'ATTENDEE' },
  { id: 9, email: 'lee@example.test', first_name: 'Lee', last_name: 'Park', role: 'ORGANIZER' },
]

async function installAdminApi(page, { role = 'ADMIN', failList = false, failPromotion = false, delayPromotion = false, delayList = false } = {}) {
  let users = attendees.map((user) => ({ ...user }))
  let promotionCount = 0
  await page.route('**/api/v1/**', async (route) => {
    const { pathname, searchParams } = new URL(route.request().url())
    const path = pathname.replace('/api/v1', '')
    const method = route.request().method()
    if (path === '/auth/me') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: { id: 1, email: 'admin@example.test', first_name: 'Ari', last_name: 'Admin', role } }) })
    }
    if (path === '/admin/users' && method === 'GET') {
      if (failList) return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'server_error', message: 'Unavailable.' } }) })
      if (delayList) await new Promise((resolve) => setTimeout(resolve, 200))
      const query = searchParams.get('q')?.toLowerCase() || ''
      const matches = users.filter((user) => `${user.first_name} ${user.last_name} ${user.email}`.toLowerCase().includes(query))
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ users: matches, pagination: { page: 1, page_size: 20, total: matches.length, total_pages: matches.length ? 1 : 0 } }) })
    }
    if (path === '/admin/users/8/promote-organizer' && method === 'POST') {
      promotionCount += 1
      if (delayPromotion) await new Promise((resolve) => setTimeout(resolve, 250))
      if (failPromotion) return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'role_conflict', message: 'The role cannot be promoted.' } }) })
      users = users.map((user) => user.id === 8 ? { ...user, role: 'ORGANIZER' } : user)
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: users.find((user) => user.id === 8) }) })
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: `Unexpected ${method} ${path}` } }) })
  })
  return () => promotionCount
}

test('administrator can search users and promote an attendee once', async ({ page }) => {
  const getPromotionCount = await installAdminApi(page)
  page.on('dialog', (dialog) => dialog.accept())
  await page.goto('/admin/users')

  await expect(page.getByRole('heading', { name: 'Usuarios y roles' })).toBeVisible()
  await expect(page.getByText('Sam Rivera')).toBeVisible()
  await expect(page.getByText('Lee Park')).toBeVisible()
  await page.getByLabel('Buscar por nombre o correo').fill('sam@')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page.getByText('Sam Rivera')).toBeVisible()
  await expect(page.getByText('Lee Park')).toHaveCount(0)

  await page.getByRole('button', { name: 'Promover a organizador' }).click()
  await expect(page.getByRole('status')).toContainText('ahora es organizador')
  await expect(page.getByText('Organizador', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Promover a organizador' })).toHaveCount(0)
  expect(getPromotionCount()).toBe(1)
})

test('non-admin cannot see the admin link or access the directory', async ({ page }) => {
  await installAdminApi(page, { role: 'ATTENDEE' })
  await page.goto('/admin/users')

  await expect(page.getByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Administración' })).toHaveCount(0)
})

test('rapid repeated promotion activation sends only one request', async ({ page }) => {
  const getPromotionCount = await installAdminApi(page, { delayPromotion: true })
  page.on('dialog', (dialog) => dialog.accept())
  await page.goto('/admin/users')
  const promoteButton = page.locator('.admin-user-card button')
  await expect(promoteButton).toBeVisible()
  await promoteButton.dispatchEvent('click')
  await promoteButton.dispatchEvent('click')
  await expect(page.getByRole('status')).toContainText('ahora es organizador')
  expect(getPromotionCount()).toBe(1)
})

test('directory loading state remains usable on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installAdminApi(page, { delayList: true })
  await page.goto('/admin/users')

  await expect(page.getByText('Cargando usuarios…')).toBeVisible()
  await expect(page.getByText('Sam Rivera')).toBeVisible()
  const dimensions = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
})

test('directory shows no matches and safely reports load and promotion errors', async ({ page }) => {
  await installAdminApi(page)
  await page.goto('/admin/users')
  await page.getByLabel('Buscar por nombre o correo').fill('absent')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page.getByText('No encontramos usuarios con esa búsqueda.')).toBeVisible()

  await page.unrouteAll()
  await installAdminApi(page, { failList: true })
  await page.goto('/admin/users')
  await expect(page.getByRole('alert')).toBeVisible()

  await page.unrouteAll()
  await installAdminApi(page, { failPromotion: true })
  await page.goto('/admin/users')
  page.on('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Promover a organizador' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
})
