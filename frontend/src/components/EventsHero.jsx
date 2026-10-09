/** Render the editorial catalogue hero and its live event search field. */

import { useState } from 'react'

const heroImageUrl =
  'https://images.unsplash.com/photo-1646265780630-b639fcc8fc28?auto=format&fit=crop&fm=jpg&q=82&w=1800'

/** Pair the discovery message with an accessible search form and photo fallback. */
export default function EventsHero({ query, onQueryChange, isSearching }) {
  const [imageUnavailable, setImageUnavailable] = useState(false)

  return (
    <section aria-labelledby="events-hero-title" className="events-hero">
      <div className="events-hero-copy">
        <p className="events-hero-kicker">Mis Eventos <span>·</span> Agenda abierta</p>
        <h1 id="events-hero-title">No te quedes <em>por fuera.</em></h1>
        <p className="events-hero-intro">Encuentra planes que conviertan un día normal en una gran historia.</p>
        <a className="events-hero-cta" href="#event-results-heading">
          Explorar agenda <span aria-hidden="true">↓</span>
        </a>
        <label className="event-search">
          <span className="visually-hidden">Busca eventos por nombre, descripción o ubicación</span>
          <span aria-hidden="true" className="event-search-icon">⌕</span>
          <input
            autoComplete="off"
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="¿Qué te gustaría vivir?"
            type="search"
            value={query}
          />
          <span aria-live="polite" className="event-search-state">
            {isSearching ? 'Buscando…' : 'Explorar'}
          </span>
        </label>
      </div>
      <div className={`events-hero-image${imageUnavailable ? ' events-hero-image-fallback' : ''}`}>
        {!imageUnavailable && (
          <img
            alt="Público disfrutando de un concierto en vivo"
            onError={() => setImageUnavailable(true)}
            src={heroImageUrl}
          />
        )}
        <div aria-hidden="true" className="events-hero-image-caption">
          <span>Encuentros que se quedan contigo</span>
          <span className="events-hero-image-mark">ME</span>
        </div>
      </div>
    </section>
  )
}
