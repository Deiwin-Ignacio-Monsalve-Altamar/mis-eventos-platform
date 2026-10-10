/** Let authenticated creators search and manage only their own events. */

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { listMyEvents } from '../api/events.js'
import EventArtwork from '../components/EventArtwork.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import useAppState from '../state/useAppState.js'
import { confirmAndDeleteEvent } from '../utils/eventDeletion.js'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

const PAGE_SIZE = 9

/** Render owner-filtered event results with real edit, cancel, and delete actions. */
export default function MyEventsPage() {
  const { saveEventChanges, removeEvent } = useAppState()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [loadState, setLoadState] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [busyEventId, setBusyEventId] = useState(null)
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const status = searchParams.get('status') || ''
  const committedQuery = searchParams.get('q') || ''
  const requestKey = `${page}:${status}:${committedQuery}:${retry}`
  const result = loadState?.key === requestKey ? loadState.data : null
  const loadError = loadState?.key === requestKey ? loadState.error : null
  const error = actionError || loadError

  useEffect(() => {
    let active = true
    listMyEvents({ page, pageSize: PAGE_SIZE, query: committedQuery, status })
      .then((data) => { if (active) setLoadState({ key: requestKey, data, error: null }) })
      .catch((requestError) => { if (active) setLoadState({ key: requestKey, data: null, error: requestError }) })
    return () => { active = false }
  }, [page, status, committedQuery, retry, requestKey])

  function updateFilters(updates) {
    setActionError(null)
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!Object.hasOwn(updates, 'page')) next.delete('page')
    setSearchParams(next)
  }

  async function cancelEvent(event) {
    if (!window.confirm(`¿Cancelar “${event.title}”? El evento conservará su historial.`)) return
    setBusyEventId(event.id)
    setActionError(null)
    try {
      await saveEventChanges(event.id, {
        title: event.title,
        description: event.description,
        location: event.location,
        starts_at: event.starts_at,
        ends_at: event.ends_at,
        capacity: event.capacity,
        status: 'cancelled',
        version: event.version,
      })
      setNotice('El evento quedó cancelado.')
      setRetry((value) => value + 1)
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setBusyEventId(null)
    }
  }

  async function deleteEvent(event) {
    setBusyEventId(event.id)
    setActionError(null)
    try {
      const deleted = await confirmAndDeleteEvent({
        eventTitle: event.title,
        confirmAction: window.confirm.bind(window),
        deleteAction: () => removeEvent(event.id),
      })
      if (deleted) {
        setNotice('El evento se eliminó correctamente.')
        setRetry((value) => value + 1)
      }
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setBusyEventId(null)
    }
  }

  return (
    <section aria-labelledby="my-events-heading" className="organizer-page">
      <header className="organizer-page-heading">
        <div><p className="eyebrow">Tu espacio de organización</p><h1 id="my-events-heading">Mis eventos</h1>
          <p>Gestiona únicamente los eventos que creaste.</p></div>
        <Link className="button button-primary" to="/events/new">Crear evento</Link>
      </header>
      <form className="organizer-filters" onSubmit={(event) => { event.preventDefault(); updateFilters({ q: query.trim() }) }}>
        <label htmlFor="my-events-search">Buscar mis eventos
          <input id="my-events-search" onChange={(event) => setQuery(event.target.value)} value={query} />
        </label>
        <label htmlFor="my-events-status">Estado
          <select id="my-events-status" onChange={(event) => updateFilters({ status: event.target.value })} value={status}>
            <option value="">Todos los estados</option>
            <option value="draft">Borrador</option><option value="published">Publicado</option>
            <option value="cancelled">Cancelado</option><option value="completed">Finalizado</option>
          </select>
        </label>
        <button className="button button-secondary" type="submit">Buscar</button>
      </form>
      {notice && <p className="feedback feedback-success" role="status">{notice}</p>}
      {error && <><ErrorMessage error={error} /><button className="button button-secondary" onClick={() => { setActionError(null); setRetry((value) => value + 1) }} type="button">Intentar de nuevo</button></>}
      {!result && !error && <LoadingMessage>Cargando tus eventos…</LoadingMessage>}
      {result?.events.length === 0 && <div className="organizer-empty"><EmptyMessage>No encontramos eventos con estos criterios.</EmptyMessage><Link className="button button-primary" to="/events/new">Crear tu primer evento</Link></div>}
      {result?.events.length > 0 && <div className="organizer-event-list">
        {result.events.map((event) => (
          <article className="organizer-event-card" key={event.id}>
            <EventArtwork title={event.title} />
            <div className="organizer-event-copy">
              <span className={`status-badge status-${event.status}`}>{getEventStatusLabel(event.status)}</span>
              <h2><Link to={`/events/${event.id}`}>{event.title}</Link></h2>
              <p><time dateTime={event.starts_at}>{formatEventDate(event.starts_at, 'medium')}</time>{event.location ? ` · ${event.location}` : ''}</p>
              <div className="button-row">
                <Link className="button button-secondary" to={`/events/${event.id}?edit=1`}>Editar</Link>
                {['draft', 'published'].includes(event.status) && <button className="button button-secondary" disabled={busyEventId === event.id} onClick={() => cancelEvent(event)} type="button">Cancelar evento</button>}
                <button className="button button-danger" disabled={busyEventId === event.id} onClick={() => deleteEvent(event)} type="button">{busyEventId === event.id ? 'Procesando…' : 'Eliminar'}</button>
              </div>
            </div>
          </article>
        ))}
      </div>}
      <PaginationControls disabled={!result} onPageChange={(nextPage) => updateFilters({ page: String(nextPage) })} pagination={result?.pagination} />
    </section>
  )
}
