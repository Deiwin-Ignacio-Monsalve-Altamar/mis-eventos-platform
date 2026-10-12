/** Verify organizer event cards select safe cover images and keep their actions. */

import { expect, test } from '@playwright/test'

const events = [
  {
    id: 31,
    title: 'Galería ordenada',
    starts_at: '2030-06-10T14:00:00Z',
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
    status: 'draft',
    images: [],
  },
  {
    id: 33,
    title: 'URL vacía',
    starts_at: '2030-06-12T14:00:00Z',
    status: 'cancelled',
    images: [{ url: '', position: 0 }],
  },
  {
    id: 34,
    title: 'URL inválida',
    starts_at: '2030-06-13T14:00:00Z',
    status: 'completed',
    images: [{ url: 'not a url', position: 0 }],
  },
  {
    id: 35,
    title: 'Fallo al cargar',
    starts_at: '2030-06-14T14:00:00Z',
    status: 'published',
    images: [{ url: 'https://images.example.test/broken.webp', position: 0 }],
  },
]

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
      await route.fulfill({
        json: {
          events,
          pagination: { page: 1, page_size: 9, total: events.length, total_pages: 1 },
        },
      })
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
  await expect(orderedCard.getByRole('heading', { name: 'Galería ordenada' })).toBeVisible()
  await expect(orderedCard.locator('.status-badge')).toHaveText('Publicado')
  await expect(orderedCard.getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/events/31?edit=1')
  await expect(orderedCard.getByRole('button', { name: 'Cancelar evento' })).toBeVisible()
  await expect(orderedCard.getByRole('button', { name: 'Eliminar' })).toBeVisible()
  await expect(orderedCard.locator('img')).not.toHaveAttribute('src', /secondary/)

  for (const title of ['Sin galería', 'URL vacía', 'URL inválida', 'Fallo al cargar']) {
    const card = page.locator('.organizer-event-row').filter({ hasText: title })
    await expect(card.locator('.event-artwork')).toBeVisible()
    await expect(card.locator('img')).toHaveCount(0)
  }

  const failedCard = page.locator('.organizer-event-row').filter({ hasText: 'Fallo al cargar' })
  await expect(failedCard.locator('.event-artwork')).toHaveText(/Mis Eventos/)
  const eventApiPaths = apiPaths.filter((path) => path.startsWith('/events/'))
  expect(eventApiPaths.length).toBeGreaterThan(0)
  expect(eventApiPaths.every((path) => path === '/events/mine')).toBe(true)
})
