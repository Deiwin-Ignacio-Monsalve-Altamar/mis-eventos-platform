/** Explore, search, and paginate the public event catalogue. */

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import EventCard from '../components/EventCard.jsx'
import EventErrorMessage from '../components/EventErrorMessage.jsx'
import EventsHero from '../components/EventsHero.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import { LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

const EVENT_PAGE_SIZE = 9
const SEARCH_DEBOUNCE_MS = 300

/** Load and render current search criteria without leaking stale results. */
export default function EventListPage() {
  const { state, refreshEvents } = useAppState()
  const { events } = state
  const [searchParams, setSearchParams] = useSearchParams()
  const routeQuery = searchParams.get('q') || ''
  const routePage = Math.max(1, Number.parseInt(searchParams.get('page') || '1', 10) || 1)
  const [debouncedQuery, setDebouncedQuery] = useState(routeQuery)
  const page = routePage
  const criteriaPending = routeQuery !== debouncedQuery
  const loading = criteriaPending || events.status === 'idle' || events.status === 'loading'

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(routeQuery), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timeout)
  }, [routeQuery])

  useEffect(() => {
    if (criteriaPending) return
    refreshEvents({ query: debouncedQuery, page, pageSize: EVENT_PAGE_SIZE })
  }, [criteriaPending, debouncedQuery, page, refreshEvents])

  function handleSearchChange(value) {
    const next = new URLSearchParams(searchParams)
    value.trim() ? next.set('q', value) : next.delete('q')
    next.delete('page')
    setSearchParams(next, { replace: true })
  }

  function changePage(nextPage) {
    const next = new URLSearchParams(searchParams)
    nextPage > 1 ? next.set('page', String(nextPage)) : next.delete('page')
    setSearchParams(next)
  }

  function retryCurrentSearch() {
    refreshEvents({ query: debouncedQuery, page, pageSize: EVENT_PAGE_SIZE })
  }

  const currentResults = !loading && events.status === 'success'
  const noResults = currentResults && events.items.length === 0

  return (
    <div className="events-page">
      <EventsHero
        isSearching={criteriaPending || events.status === 'loading'}
        onQueryChange={handleSearchChange}
        query={routeQuery}
      />

      <section aria-labelledby="event-results-heading" className="event-discovery">
        <header className="event-discovery-heading">
          <div>
            <p className="eyebrow">Una agenda para salir de la rutina</p>
            <h2 id="event-results-heading">Planes con otra energía</h2>
          </div>
          {currentResults && events.pagination && (
            <p className="event-results-count">
              {events.pagination.total} {events.pagination.total === 1 ? 'plan' : 'planes'}
            </p>
          )}
        </header>

        {loading && (
          <LoadingMessage>
            {criteriaPending ? 'Buscando eventos…' : 'Cargando eventos…'}
          </LoadingMessage>
        )}

        {!loading && events.status === 'error' && (
          <div className="event-request-error">
            <EventErrorMessage error={events.error} />
            <button className="button button-secondary" onClick={retryCurrentSearch} type="button">
              Intentar de nuevo
            </button>
          </div>
        )}

        {noResults && (
          <div className="event-empty-state">
            <p className="event-empty-mark" aria-hidden="true">∅</p>
            <p className="eyebrow">{debouncedQuery ? 'Otra búsqueda, otro plan' : 'La agenda está por comenzar'}</p>
            <h3>{debouncedQuery ? 'No encontramos coincidencias' : 'Todavía no hay eventos para mostrar'}</h3>
            <p>
              {debouncedQuery
                ? `No encontramos eventos relacionados con “${debouncedQuery}”. Prueba con otras palabras.`
                : 'Vuelve pronto para descubrir nuevos encuentros.'}
            </p>
            {debouncedQuery
              ? <button className="text-link" onClick={() => handleSearchChange('')} type="button">Limpiar búsqueda</button>
              : <Link className="text-link" to="/events/new">Organiza un evento <span aria-hidden="true">↗</span></Link>}
          </div>
        )}

        {currentResults && events.items.length > 0 && (
          <>
            <div aria-live="polite" className="event-grid">
              {events.items.map((event, index) => (
                <EventCard event={event} featured={index === 0 && page === 1 && !debouncedQuery} key={event.id} />
              ))}
            </div>
            <PaginationControls
              disabled={loading}
              onPageChange={changePage}
              pagination={events.pagination}
            />
          </>
        )}
      </section>
    </div>
  )
}
