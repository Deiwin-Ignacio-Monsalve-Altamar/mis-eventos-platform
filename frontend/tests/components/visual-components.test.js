/** Render shared visual components to verify accessible content and state variants. */

import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { test } from 'node:test'
import { createServer } from 'vite'

/** Render component variants through the existing Vite SSR test harness. */
test('event cards, pagination, sessions, artwork, and feedback render shared states', async () => {
  const vite = await createServer({
    appType: 'custom',
    configFile: 'vite.config.js',
    server: { hmr: false, middlewareMode: true, ws: false },
  })

  try {
    const [{ default: EventCard }, { default: PaginationControls }, { default: SessionList }, { default: EventArtwork }, feedback] = await Promise.all([
      vite.ssrLoadModule('/src/components/EventCard.jsx'),
      vite.ssrLoadModule('/src/components/PaginationControls.jsx'),
      vite.ssrLoadModule('/src/components/SessionList.jsx'),
      vite.ssrLoadModule('/src/components/EventArtwork.jsx'),
      vite.ssrLoadModule('/src/components/RequestFeedback.jsx'),
    ])

    const eventCard = renderToString(
      createElement(StaticRouter, { location: '/events?q=musica&page=2' }, createElement(EventCard, {
        event: {
          id: 7,
          title: 'Música al atardecer',
          description: 'Un encuentro para compartir.',
          location: 'Bogotá',
          starts_at: '2030-01-10T09:00:00Z',
          status: 'published',
          images: [
            { url: 'https://cdn.test/second.webp', position: 1 },
            { url: 'https://cdn.test/cover.webp', position: 0 },
          ],
        },
      })),
    )
    assert.match(eventCard, /Música al atardecer/)
    assert.match(eventCard, /src="https:\/\/cdn.test\/cover.webp"/)
    assert.match(eventCard, /portada del evento/)
    assert.match(eventCard, /aria-label="Ver detalles de Música al atardecer"/)
    assert.match(eventCard, /href="\/events\/7\?q=musica&amp;page=2"/)

    const pagination = renderToString(createElement(PaginationControls, {
      pagination: { page: 1, total_pages: 2, total: 10 },
      onPageChange: () => {},
    }))
    assert.match(pagination, /aria-label="Paginación de eventos"/)
    assert.match(pagination, /disabled=""/)
    assert.match(pagination, /Página <strong>1<\/strong> de <strong>2<\/strong>/)

    const loadingSessions = renderToString(createElement(SessionList, {
      eventId: 7,
      sessions: [],
      status: 'loading',
    }))
    const emptySessions = renderToString(createElement(SessionList, {
      eventId: 7,
      sessions: [],
      status: 'success',
    }))
    const failedSessions = renderToString(createElement(SessionList, {
      eventId: 7,
      sessions: [],
      status: 'error',
      error: { code: 'network_error' },
      onRetry: () => {},
    }))
    assert.match(loadingSessions, /Cargando sesiones/)
    assert.match(emptySessions, /Este evento todavía no tiene sesiones/)
    assert.match(failedSessions, /No pudimos conectar con el servidor/)
    assert.match(failedSessions, /Volver a cargar sesiones/)

    const artwork = renderToString(createElement(EventArtwork, { title: 'Música Bogotá' }))
    assert.match(artwork, /aria-hidden="true"/)
    assert.match(artwork, />MB<\/span>/)
    const [{ default: EventCover }, { default: EventImageGallery }] = await Promise.all([
      vite.ssrLoadModule('/src/components/EventCover.jsx'),
      vite.ssrLoadModule('/src/components/EventImageGallery.jsx'),
    ])
    const event = {
      title: 'Música al atardecer',
      images: [
        { url: 'https://cdn.test/second.webp', position: 1 },
        { url: 'https://cdn.test/cover.webp', position: 0 },
      ],
    }
    const detailCover = renderToString(createElement(EventCover, { event, variant: 'detail' }))
    const secondaryGallery = renderToString(createElement(EventImageGallery, { event }))
    const fallbackCover = renderToString(createElement(EventCover, { event: { title: 'Sin imágenes', images: [] }, variant: 'detail' }))
    const emptyUrlCover = renderToString(createElement(EventCover, {
      event: { title: 'URL vacía', images: [{ url: '  ', position: 0 }] },
    }))
    const invalidUrlCover = renderToString(createElement(EventCover, {
      event: { title: 'URL inválida', images: [{ url: 'javascript:alert(1)', position: 0 }] },
    }))
    assert.match(detailCover, /src="https:\/\/cdn.test\/cover.webp"/)
    assert.match(secondaryGallery, /second.webp/)
    assert.doesNotMatch(secondaryGallery, /cover.webp/)
    assert.match(fallbackCover, /event-artwork-detail/)
    assert.match(emptyUrlCover, /event-artwork-card/)
    assert.doesNotMatch(emptyUrlCover, /<img/)
    assert.match(invalidUrlCover, /event-artwork-card/)
    assert.doesNotMatch(invalidUrlCover, /<img/)
    assert.match(renderToString(createElement(feedback.LoadingMessage, null, 'Cargando perfil…')), /aria-live="polite"/)
    assert.match(renderToString(createElement(feedback.EmptyMessage, null, 'Sin inscripciones')), /Sin inscripciones/)
    assert.match(
      renderToString(createElement(feedback.ErrorMessage, { error: { code: 'network_error' } })),
      /No pudimos conectar con el servidor/,
    )
  } finally {
    await vite.close()
  }
})
