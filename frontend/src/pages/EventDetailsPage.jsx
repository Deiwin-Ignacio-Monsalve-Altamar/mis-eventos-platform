/** Present an API-backed event, its sessions, and the supported registration action. */

import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { getEventCapacity, getMyEvent } from '../api/events.js'
import { cancelMyEventRegistration, findMyEventRegistration, registerForEvent } from '../api/registrations.js'
import EventForm from '../components/EventForm.jsx'
import EventArtwork from '../components/EventArtwork.jsx'
import EventErrorMessage from '../components/EventErrorMessage.jsx'
import RegistrationNotice from '../components/RegistrationNotice.jsx'
import { ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import SessionList from '../components/SessionList.jsx'
import useAppState from '../state/useAppState.js'
import { formatEventDate, getEventStatusLabel, isEventOpenForRegistration } from '../utils/eventPresentation.js'
import { confirmAndDeleteEvent } from '../utils/eventDeletion.js'

/** Load event data and manage the real self-service registration flow. */
export default function EventDetailsPage() {
  const { eventId } = useParams()
  const { state, loadEvent, loadEventSessions, saveEventChanges, removeEvent } = useAppState()
  const { auth, selectedEvent } = state
  const { event, status, error, sessions, sessionsStatus, sessionsError } = selectedEvent
  const location = useLocation()
  const navigate = useNavigate()
  const [registration, setRegistration] = useState({ status: 'idle', error: null, registered: false })
  const [registrationCheck, setRegistrationCheck] = useState('idle')
  const [editing, setEditing] = useState(false)
  const [eventAction, setEventAction] = useState({ status: 'idle', error: null })
  const [ownerResult, setOwnerResult] = useState(null)
  const [availabilityRevision, setAvailabilityRevision] = useState(0)
  const [capacityQuery, setCapacityQuery] = useState(null)
  const registrationRequest = useRef(false)
  const ownerRequestKey = `${auth.status}:${auth.user?.id ?? ''}:${event?.id ?? ''}`
  const ownerAccess = ownerResult?.key === ownerRequestKey ? ownerResult.status : 'checking'
  const currentCapacityQuery = capacityQuery?.eventId === event?.id
    && capacityQuery?.revision === availabilityRevision
    ? capacityQuery
    : null
  const isEditing = editing || (ownerAccess === 'owner' && new URLSearchParams(location.search).get('edit') === '1')

  useEffect(() => {
    if (!/^\d+$/.test(eventId || '') || Number(eventId) < 1) return
    loadEvent(eventId)
    loadEventSessions(eventId)
  }, [eventId, loadEvent, loadEventSessions])

  useEffect(() => {
    if (!event?.id) return undefined
    let active = true
    getEventCapacity(event.id)
      .then((capacity) => {
        if (!active) return
        setCapacityQuery({ eventId: event.id, revision: availabilityRevision, status: 'success', data: capacity })
      })
      .catch(() => {
        if (active) setCapacityQuery({ eventId: event.id, revision: availabilityRevision, status: 'error', data: null })
      })
    return () => { active = false }
  }, [event?.id, availabilityRevision])

  useEffect(() => {
    if (!event?.id || auth.status !== 'authenticated') return undefined
    let active = true
    getMyEvent(event.id)
      .then(() => {
        if (active) setOwnerResult({ key: ownerRequestKey, status: 'owner' })
      })
      .catch((requestError) => {
        if (active) setOwnerResult({ key: ownerRequestKey, status: 'denied', error: requestError })
      })
    return () => { active = false }
  }, [auth.status, auth.user?.id, event?.id, ownerRequestKey])

  useEffect(() => {
    let active = true
    if (!event || auth.status !== 'authenticated') return () => { active = false }
    findMyEventRegistration(event.id)
      .then((result) => {
        if (active) {
          setRegistration((current) => ({
            ...current,
            registered: result?.status === 'registered',
            status: result?.status === 'cancelled' ? 'cancelled' : 'idle',
          }))
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

  async function handleSaveEvent(values) {
    setEventAction({ status: 'saving', error: null })
    try {
      await saveEventChanges(event.id, { ...values, version: event.version })
      setEditing(false)
      navigate(`/events/${event.id}`, { replace: true })
      setEventAction({ status: 'saved', error: null })
    } catch (requestError) {
      setEventAction({ status: 'error', error: requestError })
    }
  }

  async function handleDeleteEvent() {
    try {
      setEventAction({ status: 'deleting', error: null })
      const didDelete = await confirmAndDeleteEvent({
        eventTitle: event.title,
        confirmAction: window.confirm.bind(window),
        deleteAction: () => removeEvent(event.id),
      })
      if (!didDelete) {
        setEventAction({ status: 'idle', error: null })
        return
      }
      navigate(`/events${location.search}`, { replace: true })
    } catch (requestError) {
      setEventAction({ status: 'error', error: requestError })
    }
  }

  async function handleCancelEvent() {
    if (!window.confirm(`¿Quieres cancelar “${event.title}”? El evento conservará su historial.`)) return
    setEventAction({ status: 'saving', error: null })
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
      setEventAction({ status: 'saved', error: null })
    } catch (requestError) {
      setEventAction({ status: 'error', error: requestError })
    }
  }

  async function handleRegistration() {
    if (registrationRequest.current || registration.status === 'loading') return
    if (auth.status !== 'authenticated') {
      navigate('/login', { state: { from: `${location.pathname}${location.search}` } })
      return
    }
    registrationRequest.current = true
    setRegistration({ status: 'loading', error: null, registered: false })
    try {
      await registerForEvent(event.id)
      setAvailabilityRevision((revision) => revision + 1)
      setRegistration({ status: 'success', error: null, registered: true })
    } catch (requestError) {
      if (requestError.code === 'duplicate_registration') {
        setRegistration({ status: 'duplicate', error: null, registered: true })
      } else {
        setRegistration({ status: 'error', error: requestError, registered: false })
      }
    } finally {
      registrationRequest.current = false
    }
  }

  async function handleCancelRegistration() {
    if (registrationRequest.current || !registration.registered) return
    if (!window.confirm(`¿Cancelar tu inscripción a “${event.title}”? La plaza podría quedar disponible para otra persona.`)) return
    registrationRequest.current = true
    setRegistration({ status: 'cancelling', error: null, registered: true })
    try {
      await cancelMyEventRegistration(event.id)
      setAvailabilityRevision((revision) => revision + 1)
      setRegistration({ status: 'cancelled', error: null, registered: false })
    } catch (requestError) {
      setRegistration({ status: 'error', error: requestError, registered: true })
    } finally {
      registrationRequest.current = false
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
            <div><dt>Disponibilidad</dt><dd aria-live="polite">
              {currentCapacityQuery?.status === 'success'
                ? `${currentCapacityQuery.data.available} cupos disponibles de ${currentCapacityQuery.data.capacity}`
                : currentCapacityQuery?.status === 'error'
                  ? `Capacidad total: ${event.capacity} personas; disponibilidad no consultada`
                  : 'Consultando cupos disponibles…'}
            </dd></div>
          </dl>
          {auth.status === 'authenticated' && ownerAccess.status === 'owner' && (
            <section aria-label="Administrar evento" className="event-management">
              {isEditing ? (
                <div className="event-edit-panel">
                  <h2>Editar evento</h2>
                  <EventForm
                    error={eventAction.error}
                    event={event}
                    isSubmitting={eventAction.status === 'saving'}
                    onCancel={() => {
                      setEditing(false)
                      navigate(`/events/${event.id}`, { replace: true })
                      setEventAction({ status: 'idle', error: null })
                    }}
                    onSubmit={handleSaveEvent}
                  />
                </div>
              ) : (
                <div className="button-row event-management-actions">
                  <button
                    className="button button-secondary"
                    disabled={eventAction.status === 'deleting'}
                    onClick={() => {
                      setEventAction({ status: 'idle', error: null })
                      setEditing(true)
                    }}
                    type="button"
                  >
                    Editar evento
                  </button>
                  <button
                    className="button button-danger"
                    disabled={eventAction.status === 'deleting'}
                    onClick={handleDeleteEvent}
                    type="button"
                  >
                    {eventAction.status === 'deleting' ? 'Eliminando…' : 'Eliminar evento'}
                  </button>
                  {['draft', 'published'].includes(event.status) && (
                    <button
                      className="button button-secondary"
                      disabled={eventAction.status === 'deleting' || eventAction.status === 'saving'}
                      onClick={handleCancelEvent}
                      type="button"
                    >Cancelar evento</button>
                  )}
                </div>
              )}
              {eventAction.status === 'saved' && <p className="feedback feedback-success" role="status">Los cambios quedaron guardados.</p>}
              {eventAction.status === 'error' && !isEditing && <ErrorMessage error={eventAction.error} />}
            </section>
          )}
          {auth.status === 'anonymous' && (
            <p className="event-management-signin">
              <Link className="text-link" state={{ from: `${location.pathname}${location.search}` }} to="/login">
                Inicia sesión para administrar este evento
              </Link>
            </p>
          )}
          {(canRegister || registration.registered || registration.status === 'cancelled') && (
            <div className="event-registration">
              <RegistrationNotice registration={registration} />
              {!registration.registered && registration.status !== 'cancelled' && canRegister && (
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
              {registration.registered && (
                <button className="button button-secondary" disabled={registration.status === 'cancelling'} onClick={handleCancelRegistration} type="button">
                  {registration.status === 'cancelling' ? 'Cancelando inscripción…' : 'Cancelar inscripción'}
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
              {registrationCheck === 'error' && <p className="event-neutral-note">No pudimos consultar tus inscripciones. El servidor verificará tu estado al intentar inscribirte.</p>}
            </div>
          )}
          {!canRegister && !registration.registered && <p className="event-neutral-note">Este evento no está aceptando inscripciones.</p>}
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
          refreshKey={availabilityRevision}
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
