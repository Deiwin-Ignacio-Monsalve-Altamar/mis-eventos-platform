/** Show the authenticated user's own attendance registrations and lifecycle states. */

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { cancelMyEventRegistration, getMyRegistrationSummary, listMyRegistrations } from '../api/registrations.js'
import EventArtwork from '../components/EventArtwork.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

const PAGE_SIZE = 20

/** Render attendance information separately from events managed by the user. */
export default function MyRegistrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [loadState, setLoadState] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [busyEventId, setBusyEventId] = useState(null)
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)
  const cancellationRequest = useRef(false)
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const status = searchParams.get('status') || ''
  const period = searchParams.get('period') || ''
  const requestKey = `${page}:${status}:${period}:${retry}`
  const result = loadState?.key === requestKey ? loadState.data : null
  const summary = loadState?.key === requestKey ? loadState.summary : null
  const loadError = loadState?.key === requestKey ? loadState.error : null
  const error = actionError || loadError

  useEffect(() => {
    let active = true
    Promise.all([
      listMyRegistrations({ page, pageSize: PAGE_SIZE, status, period }),
      getMyRegistrationSummary(),
    ]).then(([registrations, activity]) => {
      if (active) setLoadState({ key: requestKey, data: registrations, summary: activity, error: null })
    }).catch((requestError) => { if (active) setLoadState({ key: requestKey, data: null, summary: null, error: requestError }) })
    return () => { active = false }
  }, [page, status, period, retry, requestKey])

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

  async function cancelRegistration(registration) {
    if (cancellationRequest.current || registration.status !== 'registered') return
    if (!window.confirm(`¿Cancelar tu inscripción a “${registration.event.title}”?`)) return
    cancellationRequest.current = true
    setBusyEventId(registration.event.id)
    setActionError(null)
    setNotice('')
    try {
      await cancelMyEventRegistration(registration.event.id)
      setNotice('Tu inscripción quedó cancelada. El evento sigue activo para otras personas.')
      setRetry((value) => value + 1)
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      cancellationRequest.current = false
      setBusyEventId(null)
    }
  }

  return (
    <section aria-labelledby="my-registrations-heading" className="organizer-page">
      <header className="organizer-page-heading">
        <div><p className="eyebrow">Tu agenda personal</p><h1 id="my-registrations-heading">Mis inscripciones</h1>
          <p>Consulta tus reservas. Una inscripción confirmada no confirma asistencia presencial.</p></div>
        <Link className="button button-secondary" to="/events">Explorar eventos</Link>
      </header>
      {summary && <dl aria-label="Resumen de inscripciones" className="activity-metrics registration-metrics">
        <Metric label="Inscripciones" value={summary.total} /><Metric label="Activas" value={summary.active} />
        <Metric label="Próximas" value={summary.upcoming} /><Metric label="Eventos pasados" value={summary.past} />
        <Metric label="Canceladas" value={summary.cancelled} />
      </dl>}
      <form className="organizer-filters" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="registration-status-filter">Estado de inscripción
          <select id="registration-status-filter" onChange={(event) => updateFilters({ status: event.target.value, period: '' })} value={status}>
            <option value="">Todos</option><option value="registered">Activa</option><option value="cancelled">Cancelada</option>
          </select>
        </label>
        <label htmlFor="registration-period-filter">Fecha del evento
          <select id="registration-period-filter" disabled={status === 'cancelled'} onChange={(event) => updateFilters({ period: event.target.value })} value={period}>
            <option value="">Todas las fechas</option><option value="upcoming">Próximos</option>
            <option value="active">En curso</option><option value="past">Pasados</option>
          </select>
        </label>
      </form>
      {notice && <p className="feedback feedback-success" role="status">{notice}</p>}
      {error && <><ErrorMessage error={error} /><button className="button button-secondary" onClick={() => { setActionError(null); setRetry((value) => value + 1) }} type="button">Intentar de nuevo</button></>}
      {!result && !error && <LoadingMessage>Cargando tus inscripciones…</LoadingMessage>}
      {result?.registrations.length === 0 && <div className="organizer-empty"><EmptyMessage>No tienes inscripciones para estos filtros.</EmptyMessage><Link className="button button-primary" to="/events">Explorar eventos</Link></div>}
      {result?.registrations.length > 0 && <div className="attendance-list">
        {result.registrations.map((registration) => <article className="attendance-card" key={registration.id}>
          <EventArtwork title={registration.event.title} />
          <div className="attendance-card-copy">
            <div className="attendance-badges">
              <span className={`status-badge status-${registration.event.status}`}>{getEventStatusLabel(registration.event.status)}</span>
              <span className={`status-badge registration-state-${registration.status}`}>{registration.status === 'registered' ? 'Inscripción activa' : 'Inscripción cancelada'}</span>
            </div>
            <h2><Link to={`/events/${registration.event.id}`}>{registration.event.title}</Link></h2>
            <p><time dateTime={registration.event.starts_at}>{formatEventDate(registration.event.starts_at)}</time></p>
            <p>{registration.event.location || 'Lugar por confirmar'}</p>
            {registration.status === 'registered' && isPast(registration.event) && <p className="attendance-note">Evento finalizado; el registro no acredita asistencia presencial.</p>}
            {registration.status === 'registered' && <button className="button button-secondary" disabled={busyEventId === registration.event.id} onClick={() => cancelRegistration(registration)} type="button">{busyEventId === registration.event.id ? 'Cancelando…' : 'Cancelar mi inscripción'}</button>}
          </div>
        </article>)}
      </div>}
      <PaginationControls disabled={!result} onPageChange={(nextPage) => updateFilters({ page: String(nextPage) })} pagination={result?.pagination} />
    </section>
  )
}

/** Render one labelled metric as a definition-list pair. */
function Metric({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>
}

/** Determine whether the event ended without treating the registration as attendance. */
function isPast(event) {
  return event.status === 'completed' || (event.status !== 'cancelled' && Date.parse(event.ends_at) <= Date.now())
}
