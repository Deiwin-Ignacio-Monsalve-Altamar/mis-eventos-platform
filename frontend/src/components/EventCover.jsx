/** Render position zero as the event cover, with the branded artwork fallback. */
import EventArtwork from './EventArtwork.jsx'

function getEventCoverImage(event) {
  return (event.images || []).find((image) => image.position === 0) || null
}

export default function EventCover({ event, variant = 'card' }) {
  const cover = getEventCoverImage(event)
  if (!cover) return <EventArtwork title={event.title} variant={variant} />

  return (
    <img
      alt={`${event.title}, portada del evento`}
      className={`event-cover event-cover-${variant}`}
      src={cover.url}
    />
  )
}
