/** Show the current profile loaded from the authenticated API endpoint. */

import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getMyEventDashboard, listMyEvents } from '../api/events.js'
import { cancelMyEventRegistration, getMyRegistrationSummary, listMyRegistrations } from '../api/registrations.js'
import AuthErrorMessage from '../components/AuthErrorMessage.jsx'
import EventArtwork from '../components/EventArtwork.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'
import { getEventStatusLabel } from '../utils/eventPresentation.js'

/** Render the user's public identity and API-backed event registrations. */
export default function ProfilePage() {
  const { state, signOut } = useAppState()
  const navigate = useNavigate()
  const { auth } = state
  const [registrationQuery, setRegistrationQuery] = useState(null)
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [activityResponse, setActivityResponse] = useState(null)
  const [activityRetry, setActivityRetry] = useState(0)
  const [logoutBusy, setLogoutBusy] = useState(false)
  const [logoutError, setLogoutError] = useState(null)
  const [registrationBusyId, setRegistrationBusyId] = useState(null)
  const [registrationActionError, setRegistrationActionError] = useState(null)
  const [registrationActionNotice, setRegistrationActionNotice] = useState('')
  const logoutRequest = useRef(false)
  const cancellationRequest = useRef(false)
  const activityKey = `${auth.user?.id ?? 'anonymous'}:${activityRetry}`
  const activity = activityResponse?.key === activityKey ? activityResponse.data : null
  const activityError = activityResponse?.key === activityKey ? activityResponse.error : null
  const queryKey = `${auth.user?.id ?? 'anonymous'}:${page}:${refresh}`
  const registrations = registrationQuery?.key === queryKey ? registrationQuery.data : null
  const registrationError = registrationQuery?.key === queryKey ? registrationQuery.error : null

  useEffect(() => {
    if (auth.status !== 'authenticated') return undefined
    let active = true
    listMyRegistrations({ page, pageSize: 20 })
      .then((result) => {
        if (active) setRegistrationQuery({ key: queryKey, data: result, error: null })
      })
      .catch((error) => {
        if (active) setRegistrationQuery({ key: queryKey, data: null, error })
      })
    return () => {
      active = false
    }
  }, [auth.status, page, queryKey])

  useEffect(() => {
    if (auth.status !== 'authenticated') return undefined
    let active = true
    Promise.all([
      getMyEventDashboard(),
      getMyRegistrationSummary(),
      listMyEvents({ page: 1, pageSize: 3 }),
    ]).then(([created, attending, ownEvents]) => {
      if (active) setActivityResponse({
        key: activityKey,
        data: { created, attending, ownEvents: ownEvents.events },
        error: null,
      })
    }).catch((error) => {
      if (active) setActivityResponse({ key: activityKey, data: null, error })
    })
    return () => { active = false }
  }, [auth.status, auth.user?.id, activityRetry, activityKey])

  async function handleLogout() {
    if (logoutRequest.current) return
    logoutRequest.current = true
    setLogoutBusy(true)
    setLogoutError(null)
    try {
      await signOut()
      navigate('/login', { replace: true })
    } catch (error) {
      setLogoutError(error)
    } finally {
      logoutRequest.current = false
      setLogoutBusy(false)
    }
  }

  async function handleCancelRegistration(registration) {
    if (cancellationRequest.current || registration.status !== 'registered') return
    if (!window.confirm(`¿Cancelar tu inscripción a “${registration.event.title}”? La plaza podría quedar disponible para otra persona.`)) return
    cancellationRequest.current = true
    setRegistrationBusyId(registration.event.id)
    setRegistrationActionError(null)
    setRegistrationActionNotice('')
    try {
      await cancelMyEventRegistration(registration.event.id)
      setRegistrationActionNotice('Tu inscripción quedó cancelada.')
      setRefresh((current) => current + 1)
      setActivityRetry((current) => current + 1)
    } catch (error) {
      setRegistrationActionError(error)
    } finally {
      cancellationRequest.current = false
      setRegistrationBusyId(null)
    }
  }

  if (auth.status === 'loading') {
    return <LoadingMessage>Estamos cargando tu perfil…</LoadingMessage>
  }
  if (auth.status === 'error') {
    return (
      <section className="content-panel profile-recovery">
        <p className="eyebrow">Tu cuenta</p>
        <h1>Tu perfil no está disponible</h1>
        <AuthErrorMessage error={auth.error} />
        <Link className="button button-secondary" to="/login">Volver a iniciar sesión</Link>
      </section>
    )
  }
  if (auth.status !== 'authenticated') {
    return (
      <section className="content-panel profile-recovery">
        <p className="eyebrow">Tu cuenta</p>
        <h1>Inicia sesión para ver tu perfil</h1>
        <p>Cuando inicies sesión podrás consultar la información de tu cuenta.</p>
        <div className="button-row">
          <Link className="button button-primary" to="/login">Iniciar sesión</Link>
          <Link className="button button-secondary" to="/register">Crear una cuenta</Link>
        </div>
      </section>
    )
  }

  return (
    <div className="profile-page">
      <header className="profile-hero">
        <div aria-hidden="true" className="profile-avatar">{getInitials(auth.user.first_name, auth.user.last_name)}</div>
        <div className="profile-identity">
          <p className="eyebrow">Tu cuenta</p>
          <h1>Te damos la bienvenida, {auth.user.first_name}</h1>
          <p>{auth.user.email}</p>
          <button className="button button-secondary" disabled={logoutBusy} onClick={handleLogout} type="button">
            {logoutBusy ? 'Cerrando sesión…' : 'Cerrar sesión'}
          </button>
        </div>
        <p className="profile-welcome-note">Los buenos momentos empiezan cuando hacemos espacio para encontrarnos.</p>
      </header>
      {logoutError && <ErrorMessage error={logoutError} />}

      <section aria-labelledby="activity-heading" className="profile-activity">
        <div className="profile-section-heading">
          <div><p className="eyebrow">Tu actividad</p><h2 id="activity-heading">Crear y asistir</h2></div>
          <div className="button-row">
            <Link className="button button-primary" to="/events/new">Crear evento</Link>
            <Link className="button button-secondary" to="/my-events">Mis eventos</Link>
            <Link className="button button-secondary" to="/my-registrations">Mis inscripciones</Link>
          </div>
        </div>

        {registrationActionNotice && <p className="feedback feedback-success" role="status">{registrationActionNotice}</p>}
        {registrationActionError && <ErrorMessage error={registrationActionError} />}
        {!activity && !activityError && <LoadingMessage>Cargando el resumen de tu actividad…</LoadingMessage>}
        {activityError && <div><ErrorMessage error={activityError} /><button className="button button-secondary" onClick={() => setActivityRetry((value) => value + 1)} type="button">Intentar de nuevo</button></div>}
        {activity && <>
          <h3 className="activity-group-heading">Eventos que has creado</h3>
          <dl aria-label="Estadísticas de eventos creados" className="activity-metrics">
            <Metric label="Total creados" value={activity.created.total_events} />
            <Metric label="Próximos" value={activity.created.upcoming_events} />
            <Metric label="En curso" value={activity.created.active_events} />
            <Metric label="Finalizados" value={activity.created.finished_events} />
            <Metric label="Cancelados" value={activity.created.cancelled_events} />
          </dl>
          <div aria-label="Porcentaje de eventos por estado" className="event-status-chart">
            {Object.entries(activity.created.status_counts).map(([status, count]) => (
              <div className="event-status-chart-row" key={status}>
                <span>{getEventStatusLabel(status)}</span>
                <div aria-label={`${getEventStatusLabel(status)}: ${activity.created.status_percentages[status]} por ciento`} aria-valuemax="100" aria-valuemin="0" aria-valuenow={activity.created.status_percentages[status]} className="event-status-track" role="progressbar">
                  <span style={{ width: `${activity.created.status_percentages[status]}%` }} />
                </div>
                <strong>{count}</strong>
              </div>
            ))}
            <p>Porcentajes calculados sobre {activity.created.total_events} eventos creados.</p>
          </div>
          {activity.ownEvents.length === 0
            ? <div className="profile-empty-state"><EmptyMessage>Aún no has creado eventos.</EmptyMessage><Link className="button button-primary" to="/events/new">Crear tu primer evento</Link></div>
            : <div className="profile-owned-events">{activity.ownEvents.map((event) => <article className="profile-owned-event" key={event.id}>
              <EventArtwork title={event.title} />
              <div><span className={`status-badge status-${event.status}`}>{getEventStatusLabel(event.status)}</span><h4><Link to={`/events/${event.id}`}>{event.title}</Link></h4></div>
              <Link className="text-link" to={`/events/${event.id}?edit=1`}>Gestionar</Link>
            </article>)}</div>}
          <h3 className="activity-group-heading">Eventos a los que te has inscrito</h3>
          <dl aria-label="Estadísticas de inscripciones" className="activity-metrics registration-metrics">
            <Metric label="Inscripciones" value={activity.attending.total} />
            <Metric label="Activas" value={activity.attending.active} />
            <Metric label="Próximas" value={activity.attending.upcoming} />
            <Metric label="Eventos pasados" value={activity.attending.past} />
            <Metric label="Canceladas" value={activity.attending.cancelled} />
          </dl>
          <p className="attendance-note">Los eventos pasados reflejan una inscripción confirmada; no acreditan asistencia presencial.</p>
        </>}
      </section>

      <section aria-labelledby="registrations-heading" className="profile-registrations">
        <div className="profile-section-heading">
          <div>
            <p className="eyebrow">Tu vida de eventos</p>
            <h2 id="registrations-heading">Inscripciones recientes</h2>
          </div>
          {registrations && <p className="registration-count">{registrations.pagination.total} en total</p>}
        </div>

        {!registrations && !registrationError && <LoadingMessage>Estamos cargando tus inscripciones…</LoadingMessage>}
        {registrationError && (
          <div className="profile-load-error">
            <AuthErrorMessage error={registrationError} />
            {registrationError.status === 401
              ? <Link className="button button-secondary" to="/login">Iniciar sesión nuevamente</Link>
              : <button className="button button-secondary" onClick={() => setRefresh((current) => current + 1)} type="button">Intentar de nuevo</button>}
          </div>
        )}
        {registrations?.registrations.length === 0 && (
          <div className="profile-empty-state">
            <EmptyMessage>Aún no tienes inscripciones a eventos.</EmptyMessage>
            <Link className="button button-primary" to="/events">Explorar eventos</Link>
          </div>
        )}
        {registrations?.registrations.length > 0 && (
          <>
            <ul className="registration-list">
              {registrations.registrations.map((registration) => (
                <li className="registration-item" key={registration.id}>
                  <time aria-label={`Comienza el ${formatEventDate(registration.event.starts_at)}`} className="registration-date" dateTime={registration.event.starts_at}>
                    <span>{formatMonth(registration.event.starts_at)}</span>
                    <strong>{formatDay(registration.event.starts_at)}</strong>
                  </time>
                  <div className="registration-details">
                    <Link className="registration-title" to={`/events/${registration.event.id}`}>
                      {registration.event.title}
                    </Link>
                    <p>{registration.event.location}</p>
                    <span className={`status-badge status-${registration.event.status}`}>{getEventStatusLabel(registration.event.status)}</span>
                  </div>
                  <span className={`registration-status status-${registration.status}`}>
                    {registration.status === 'registered' ? 'Inscrito' : 'Cancelada'}
                  </span>
                  {registration.status === 'registered' && (
                    <button className="button button-secondary" disabled={registrationBusyId === registration.event.id} onClick={() => handleCancelRegistration(registration)} type="button">
                      {registrationBusyId === registration.event.id ? 'Cancelando…' : 'Cancelar inscripción'}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {registrations.pagination.total_pages > 1 && (
              <nav aria-label="Páginas de inscripciones" className="profile-pagination">
                <button className="button button-secondary" disabled={page <= 1} onClick={() => setPage((currentPage) => currentPage - 1)} type="button">Anterior</button>
                <span>Página {page} de {registrations.pagination.total_pages}</span>
                <button className="button button-secondary" disabled={page >= registrations.pagination.total_pages} onClick={() => setPage((currentPage) => currentPage + 1)} type="button">Siguiente</button>
              </nav>
            )}
            <p className="form-footnote"><Link to="/my-registrations">Ver y filtrar todas mis inscripciones</Link></p>
          </>
        )}
      </section>
    </div>
  )
}

/** Render one concise organizer or attendance metric. */
function Metric({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>
}

/** Return initials for the profile avatar using the authenticated public name. */
function getInitials(firstName, lastName) {
  return `${firstName?.[0] || ''}${lastName?.[0] || ''}`.toUpperCase()
}

/** Format the event start date for the registration date tile. */
function formatEventDate(value) {
  return new Intl.DateTimeFormat('es', { dateStyle: 'long' }).format(new Date(value))
}

/** Return a short month label for an event start date. */
function formatMonth(value) {
  return new Intl.DateTimeFormat('es', { month: 'short' }).format(new Date(value))
}

/** Return the numeric day label for an event start date. */
function formatDay(value) {
  return new Intl.DateTimeFormat('es', { day: '2-digit' }).format(new Date(value))
}
