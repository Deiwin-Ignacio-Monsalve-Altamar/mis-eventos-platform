/** Present an API-backed event, its sessions, and the supported registration action. */

import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { findMyEventRegistration, registerForEvent } from '../api/registrations.js'
import EventArtwork from '../components/EventArtwork.jsx'
import EventErrorMessage from '../components/EventErrorMessage.jsx'
import { LoadingMessage } from '../components/RequestFeedback.jsx'
import SessionList from '../components/SessionList.jsx'
import useAppState from '../state/useAppState.js'
import { formatEventDate, getEventStatusLabel, isEventOpenForRegistration } from '../utils/eventPresentation.js'

/** Load event data and manage the real self-service registration flow. */
export default function EventDetailsPage() {
  const { eventId } = useParams()
  const { state, loadEvent, loadEventSessions } = useAppState()
  const { auth, selectedEvent } = state
  const { event, status, error, sessions, sessionsStatus, sessionsError } = selectedEvent
  const location = useLocation()
  const navigate = useNavigate()
  const [registration, setRegistration] = useState({ status: 'idle', error: null, registered: false })
  const [registrationCheck, setRegistrationCheck] = useState('idle')

  useEffect(() => {
    if (!/^\d+$/.test(eventId || '') || Number(eventId) < 1) return
    loadEvent(eventId)
    loadEventSessions(eventId)
  }, [eventId, loadEvent, loadEventSessions])

  useEffect(() => {
    let active = true
    if (!event || auth.status !== 'authenticated') return () => { active = false }
    findMyEventRegistration(event.id)
      .then((result) => {
        if (active) {
          setRegistration((current) => ({ ...current, registered: result?.status === 'registered' }))
          setRegistrationCheck('complete')
        }
      })
      .catch(() => {
        if (active) setRegistrationCheck('error')
      })
    return () => { active = false }
  }, [auth.status, event])

  if (!/^\d+$/.test(eventId || '') || Number(eventId) < 1) {
    return <EventUnavailable onBack={() => navigate('/events')} />
  }
  if (status === 'loading' || status === 'idle') return <LoadingMessage>Estamos cargando el evento…</LoadingMessage>
  if (status === 'error') {
    return (
      <section className="event-detail-state">
        <EventErrorMessage error={error} />
        <Link className="text-link" to={`/events${location.search}`}>← Volver a eventos</Link>
      </section>
    )
  }
  if (!event) return <EventUnavailable onBack={() => navigate('/events')} />

  const canRegister = isEventOpenForRegistration(event)

  async function handleRegistration() {
    if (auth.status !== 'authenticated') {
      navigate('/login', { state: { from: `${location.pathname}${location.search}` } })
      return
    }
    setRegistration({ status: 'loading', error: null, registered: false })
    try {
      await registerForEvent(event.id)
      setRegistration({ status: 'success', error: null, registered: true })
    } catch (requestError) {
      setRegistration({ status: 'error', error: requestError, registered: false })
    }
  }

  return (
    <div className="event-detail-page">
      <Link className="text-link event-back-link" to={`/events${location.search}`}>← Volver a eventos</Link>
      <article className="event-detail-editorial">
        <EventArtwork title={event.title} variant="detail" />
        <div className="event-detail-copy">
          <p className="eyebrow">{getEventStatusLabel(event.status)}</p>
          <h1>{event.title}</h1>
          <p className="event-description">{event.description || 'La organización aún no ha compartido una descripción.'}</p>
          <dl className="event-facts">
            <div><dt>Fecha</dt><dd><time dateTime={event.starts_at}>{formatEventDate(event.starts_at)}</time></dd></div>
            <div><dt>Finaliza</dt><dd><time dateTime={event.ends_at}>{formatEventDate(event.ends_at)}</time></dd></div>
            <div><dt>Lugar</dt><dd>{event.location || 'Lugar por confirmar'}</dd></div>
            <div><dt>Capacidad</dt><dd>{event.capacity} personas</dd></div>
          </dl>
          {canRegister && (
            <div className="event-registration">
              {registration.registered ? (
                <p className="feedback feedback-success" role="status">Ya tienes una inscripción activa para este evento.</p>
              ) : (
                <button
                  aria-busy={registration.status === 'loading'}
                  className="button button-primary"
                  disabled={registration.status === 'loading' || auth.status === 'loading' || (auth.status === 'authenticated' && registrationCheck === 'idle')}
                  onClick={handleRegistration}
                  type="button"
                >
                  {registration.status === 'loading' ? 'Inscribiéndote…' : 'Inscribirme al evento'}
                </button>
              )}
              {registration.status === 'error' && (
                <>
                  <EventErrorMessage error={registration.error} />
                  {registration.error?.status === 401 && (
                    <Link className="text-link" to="/login" state={{ from: `${location.pathname}${location.search}` }}>
                      Iniciar sesión para continuar
                    </Link>
                  )}
                </>
              )}
              {registration.status === 'success' && <p className="feedback feedback-success" role="status">Tu inscripción quedó confirmada.</p>}
              {registrationCheck === 'error' && <p className="event-neutral-note">No pudimos consultar tus inscripciones. El servidor verificará tu estado al intentar inscribirte.</p>}
            </div>
          )}
          {!canRegister && <p className="event-neutral-note">Este evento no está aceptando inscripciones.</p>}
        </div>
      </article>

      <section aria-labelledby="sessions-heading" className="event-sessions-section">
        <header><p className="eyebrow">La agenda</p><h2 id="sessions-heading">Sesiones del evento</h2></header>
        <SessionList
          error={sessionsError}
          eventId={event.id}
          onRetry={() => loadEventSessions(event.id)}
          sessions={sessions}
          status={sessionsStatus}
        />
      </section>
    </div>
  )
}

/** Explain that an invalid or missing event identifier has no matching event. */
function EventUnavailable({ onBack }) {
  return (
    <section className="event-detail-state">
      <p className="eyebrow">Evento no disponible</p>
      <h1>No encontramos este evento</h1>
      <p>El enlace puede estar incompleto o el evento ya no está disponible.</p>
      <button className="button button-secondary" onClick={onBack} type="button">Volver al listado</button>
    </section>
  )
}
