/** Present an API-backed event as an editorial link from the event catalogue. */

import { Link, useLocation } from 'react-router-dom'
import EventArtwork from './EventArtwork.jsx'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

/** Render event data with a clearly decorative fallback instead of a fake photo. */
export default function EventCard({ event, featured = false }) {
  const location = useLocation()
  return (
    <article className={`event-card${featured ? ' event-card-featured' : ''}`}>
      <EventArtwork title={event.title} />
      <div className="event-card-content">
        <div className="event-card-meta">
          <span className={`status-badge status-${event.status}`}>
            {getEventStatusLabel(event.status)}
          </span>
          <time dateTime={event.starts_at}>{formatEventDate(event.starts_at, 'medium')}</time>
        </div>
        <h3>{event.title}</h3>
        <p className="event-card-description">
          {event.description || 'La información de este evento se anunciará próximamente.'}
        </p>
        {event.location && <p className="event-location">{event.location}</p>}
        <Link aria-label={`Ver detalles de ${event.title}`} className="text-link" to={`/events/${event.id}${location.search}`}>
          Ver evento <span aria-hidden="true">↗</span>
        </Link>
      </div>
    </article>
  )
}
