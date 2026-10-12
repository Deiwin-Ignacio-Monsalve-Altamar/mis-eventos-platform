/** Render position zero as the event cover, with the branded artwork fallback. */
import { useState } from 'react'
import EventArtwork from './EventArtwork.jsx'

function getEventCoverImage(event) {
  if (!Array.isArray(event.images)) return null
  return [...event.images]
    .filter((image) => image?.position === 0)
    .sort((left, right) => left.position - right.position)[0] || null
}

function getValidImageUrl(image) {
  if (typeof image?.url !== 'string' || !image.url.trim()) return null
  try {
    const url = new URL(image.url.trim())
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null
  } catch {
    return null
  }
}

export default function EventCover({ event, variant = 'card' }) {
  const cover = getEventCoverImage(event)
  const coverUrl = getValidImageUrl(cover)
  const [failedUrl, setFailedUrl] = useState(null)

  if (!coverUrl || failedUrl === coverUrl) {
    return <EventArtwork title={event.title} variant={variant} />
  }

  return (
    <img
      alt={`${event.title}, portada del evento`}
      className={`event-cover event-cover-${variant}${variant === 'organizer' ? ' organizer-event-cover' : ''}`}
      onError={() => setFailedUrl(coverUrl)}
      src={coverUrl}
    />
  )
}
