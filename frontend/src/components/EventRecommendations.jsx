/** Show backend-verified available events in a keyboard and touch friendly carousel. */

import { useRef } from 'react'
import { Link } from 'react-router-dom'
import EventArtwork from './EventArtwork.jsx'
import { ErrorMessage, LoadingMessage } from './RequestFeedback.jsx'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

/** Render a horizontal event rail with actionable controls and honest empty states. */
export default function EventRecommendations({ recommendations, error, loading }) {
  const railRef = useRef(null)

  function scroll(direction) {
    const rail = railRef.current
    const card = rail?.querySelector('.recommendation-card')
    if (!rail || !card) return
    rail.scrollBy({ left: direction * (card.getBoundingClientRect().width + 16), behavior: 'smooth' })
  }

  return (
    <section aria-labelledby="recommendations-heading" className="recommendations-section">
      <div className="profile-section-heading">
        <div><p className="eyebrow">Descubre algo nuevo</p><h2 id="recommendations-heading">Eventos que podrían gustarte</h2>
          <p>Próximos eventos publicados con cupos disponibles.</p></div>
        {recommendations?.length > 1 && <div aria-label="Controles de recomendaciones" className="recommendation-controls">
          <button aria-label="Ver eventos anteriores" className="button button-secondary" onClick={() => scroll(-1)} type="button">←</button>
          <button aria-label="Ver eventos siguientes" className="button button-secondary" onClick={() => scroll(1)} type="button">→</button>
        </div>}
      </div>
      {loading && <LoadingMessage>Buscando próximos eventos…</LoadingMessage>}
      {error && <ErrorMessage error={error} />}
      {!loading && !error && recommendations?.length === 0 && <div className="recommendations-empty">
        <p>Por ahora no encontramos eventos próximos con cupos disponibles.</p>
        <Link className="button button-primary" to="/events">Explorar todos los eventos</Link>
      </div>}
      {!loading && !error && recommendations?.length > 0 && <div aria-label="Recomendaciones de eventos" className="recommendation-rail" ref={railRef} role="list" tabIndex="0">
        {recommendations.map(({ event }) => (
          <article className="recommendation-card" key={event.id} role="listitem">
            <EventArtwork title={event.title} />
            <div className="recommendation-card-copy">
              <span className="availability-badge availability-available">Cupos disponibles</span>
              <h3><Link to={`/events/${event.id}`}>{event.title}</Link></h3>
              <p><time dateTime={event.starts_at}>{formatEventDate(event.starts_at, 'medium')}</time></p>
              {event.description && <p className="recommendation-description">{event.description}</p>}
              <Link className="text-link" to={`/events/${event.id}`}>Conocer evento</Link>
            </div>
            <span className="recommendation-status">{getEventStatusLabel(event.status)}</span>
          </article>
        ))}
      </div>}
    </section>
  )
}
