/** Let authenticated creators search and manage only their own events. */

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getMyEventMetrics, listEventSessions, listMyEvents } from '../api/events.js'
import EventCover from '../components/EventCover.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import ProfileMetricGrid from '../components/ProfileMetricGrid.jsx'
import useAppState from '../state/useAppState.js'
import { confirmAndDeleteEvent } from '../utils/eventDeletion.js'
import { formatEventDate, getEventStatusLabel, sortSessions } from '../utils/eventPresentation.js'

const PAGE_SIZE = 9

/** Render owner-filtered event results with real edit, cancel, and delete actions. */
export default function MyEventsPage() {
  const { saveEventChanges, removeEvent } = useAppState()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [loadState, setLoadState] = useState(null)
  const [metricsState, setMetricsState] = useState(null)
  const [upcomingSessionState, setUpcomingSessionState] = useState({ key: '', items: {} })
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
  const metricsByEventId = new Map((metricsState?.data?.events || []).map((event) => [event.id, event]))
  const hasFilters = Boolean(committedQuery || status)

  useEffect(() => {
    let active = true
    listMyEvents({ page, pageSize: PAGE_SIZE, query: committedQuery, status })
      .then((data) => { if (active) setLoadState({ key: requestKey, data, error: null }) })
      .catch((requestError) => { if (active) setLoadState({ key: requestKey, data: null, error: requestError }) })
    return () => { active = false }
  }, [page, status, committedQuery, retry, requestKey])

  useEffect(() => {
    let active = true
    getMyEventMetrics()
      .then((data) => { if (active) setMetricsState({ data, error: null }) })
      .catch((requestError) => { if (active) setMetricsState({ data: null, error: requestError }) })
    return () => { active = false }
  }, [retry])

  const publishedEvents = (result?.events || []).filter((event) => event.status === 'published')
  const upcomingEventKey = publishedEvents.map((event) => event.id).join(',')
  const upcomingSessions = upcomingSessionState.key === upcomingEventKey ? upcomingSessionState.items : {}

  useEffect(() => {
    let active = true
    if (!upcomingEventKey) return () => { active = false }
    const eventIds = upcomingEventKey.split(',')
    Promise.all(eventIds.map(async (eventId) => {
      try {
        const sessions = await listEventSessions(eventId)
        const nextSession = sortSessions(sessions).find((session) => Date.parse(session.starts_at) > Date.now()) || null
        return [eventId, { status: 'success', session: nextSession }]
      } catch {
        return [eventId, { status: 'error', session: null }]
      }
    })).then((entries) => {
      if (active) setUpcomingSessionState({ key: upcomingEventKey, items: Object.fromEntries(entries) })
    })
    return () => { active = false }
  }, [upcomingEventKey])

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
      {metricsState?.error && !['authentication_required', 'forbidden'].includes(metricsState.error.code) && (
        <div className="organizer-metrics-error">
          <ErrorMessage error={metricsState.error} />
          <button className="button button-secondary" onClick={() => setRetry((value) => value + 1)} type="button">Volver a cargar indicadores</button>
        </div>
      )}
      {!metricsState?.data && !metricsState?.error && <LoadingMessage>Cargando indicadores de tus eventos…</LoadingMessage>}
      {metricsState?.data?.summary && (
        <ProfileMetricGrid label="Indicadores de tus eventos" metrics={[
          { label: 'Eventos creados', value: metricsState.data.summary.total_events },
          { label: 'Próximos', value: metricsState.data.summary.upcoming_events },
          { label: 'En curso', value: metricsState.data.summary.active_events },
          { label: 'Inscripciones activas', value: metricsState.data.summary.active_registrations },
        ]} />
      )}
      {notice && <p className="feedback feedback-success" role="status">{notice}</p>}
      {error && <><ErrorMessage error={error} /><button className="button button-secondary" onClick={() => { setActionError(null); setRetry((value) => value + 1) }} type="button">Intentar de nuevo</button></>}
      {!result && !error && <LoadingMessage>Cargando tus eventos…</LoadingMessage>}
      {result?.events.length === 0 && <div className="organizer-empty">
        <EmptyMessage>{hasFilters ? 'No encontramos eventos con estos criterios. Prueba otra búsqueda o limpia los filtros.' : 'Aún no has creado eventos.'}</EmptyMessage>
        {hasFilters && <button className="button button-secondary" onClick={() => { setQuery(''); updateFilters({ q: '', status: '' }) }} type="button">Limpiar filtros</button>}
        <Link className="button button-primary" to="/events/new">Crear evento</Link>
      </div>}
      {result?.events.length > 0 && <div className="organizer-events-table-wrap">
        <table className="organizer-events-table">
          <caption>Tus eventos, agenda próxima e indicadores disponibles</caption>
          <thead><tr><th scope="col">Evento</th><th scope="col">Estado</th><th scope="col">Fecha y lugar</th><th scope="col">Actividad</th><th scope="col">Acciones</th></tr></thead>
          <tbody>{result.events.map((event) => (
            <tr className="organizer-event-row" key={event.id}>
              <th data-label="Evento" scope="row">
                <div className="organizer-event-primary">
                  <EventCover event={event} variant="organizer" />
                  <h2><Link to={`/events/${event.id}`}>{event.title}</Link></h2>
                </div>
              </th>
              <td data-label="Estado"><span className={`status-badge status-${event.status}`}>{getEventStatusLabel(event.status)}</span></td>
              <td data-label="Fecha y lugar"><time dateTime={event.starts_at}>{formatEventDate(event.starts_at, 'medium')}</time>{event.location && <span className="organizer-event-location">{event.location}</span>}</td>
              <td data-label="Actividad">
                {metricsByEventId.has(event.id) ? <OrganizerEventActivity event={event} metrics={metricsByEventId.get(event.id)} upcoming={upcomingSessions[event.id]} /> : <span>Indicadores no disponibles</span>}
              </td>
              <td data-label="Acciones"><div className="organizer-row-actions">
                <Link className="button button-secondary" to={`/events/${event.id}?edit=1`}>Editar</Link>
                {['draft', 'published'].includes(event.status) && <button className="button button-secondary" disabled={busyEventId === event.id} onClick={() => cancelEvent(event)} type="button">Cancelar evento</button>}
                <button className="button button-danger" disabled={busyEventId === event.id} onClick={() => deleteEvent(event)} type="button">{busyEventId === event.id ? 'Procesando…' : 'Eliminar'}</button>
              </div></td>
            </tr>
          ))}</tbody>
        </table>
      </div>}
      <PaginationControls disabled={!result} onPageChange={(nextPage) => updateFilters({ page: String(nextPage) })} pagination={result?.pagination} />
    </section>
  )
}

/** Show only owner-scoped measurements returned by the event management APIs. */
function OrganizerEventActivity({ event, metrics, upcoming }) {
  return (
    <div className="organizer-event-activity">
      <span>{metrics.session_count} {metrics.session_count === 1 ? 'sesión' : 'sesiones'}</span>
      <span>{metrics.active_registrations} {metrics.active_registrations === 1 ? 'inscripción activa' : 'inscripciones activas'}</span>
      <span>{metrics.available_seats} {metrics.available_seats === 1 ? 'cupo libre' : 'cupos libres'}</span>
      {event.status === 'published' && (!upcoming || upcoming.status === 'loading') && <span>Consultando próxima sesión…</span>}
      {event.status === 'published' && upcoming?.status === 'error' && <span>Agenda no disponible</span>}
      {event.status === 'published' && upcoming?.status === 'success' && (upcoming.session
        ? <span>Próxima: {upcoming.session.title} · {formatEventDate(upcoming.session.starts_at, 'medium')}</span>
        : <span>Sin próximas sesiones</span>)}
    </div>
  )
}
