/** Present an API-backed event, its sessions, and the supported registration action. */

import { useEffect, useReducer, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { createEventSession, deleteEventSession, getEventCapacity, getMyEvent, updateEventSession } from '../api/events.js'
import { cancelMyEventRegistration, findMyEventRegistration, registerForEvent } from '../api/registrations.js'
import EventForm from '../components/EventForm.jsx'
import EventArtwork from '../components/EventArtwork.jsx'
import EditorModal from '../components/EditorModal.jsx'
import EventErrorMessage from '../components/EventErrorMessage.jsx'
import RegistrationNotice from '../components/RegistrationNotice.jsx'
import { ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import SessionList from '../components/SessionList.jsx'
import SessionForm from '../components/SessionForm.jsx'
import RegistrationActions from '../components/RegistrationActions.jsx'
import useAppState from '../state/useAppState.js'
import { formatEventDate, getEventStatusLabel, isEventOpenForRegistration } from '../utils/eventPresentation.js'
import { confirmAndDeleteEvent } from '../utils/eventDeletion.js'
import { canManageEvent } from '../utils/eventPermissions.js'
import { initialRegistrationState, registrationReducer } from '../state/registrationReducer.js'
import { getEventEditorLocation } from '../utils/eventEditorLocation.js'

/** Load event data and manage the real self-service registration flow. */
export default function EventDetailsPage() {
  const { eventId } = useParams()
  const { state, loadEvent, loadEventSessions, saveEventChanges, removeEvent } = useAppState()
  const { auth, selectedEvent } = state
  const { event, status, error, sessions, sessionsStatus, sessionsError } = selectedEvent
  const location = useLocation()
  const navigate = useNavigate()
  const [registrationState, dispatchRegistration] = useReducer(registrationReducer, initialRegistrationState)
  const [eventAction, setEventAction] = useState({ status: 'idle', error: null })
  const [ownerResult, setOwnerResult] = useState(null)
  const [availabilityRevision, setAvailabilityRevision] = useState(0)
  const [registrationRevision, setRegistrationRevision] = useState(0)
  const [capacityQuery, setCapacityQuery] = useState(null)
  const [sessionEditor, setSessionEditor] = useState(undefined)
  const [sessionAction, setSessionAction] = useState({ status: 'idle', error: null, deletingId: null })
  const registrationRequest = useRef(false)
  const sessionRequest = useRef(false)
  const ownerRequestKey = `${auth.status}:${auth.user?.id ?? ''}:${event?.id ?? ''}`
  const ownerAccess = ownerResult?.key === ownerRequestKey ? ownerResult.status : 'checking'
  const currentCapacityQuery = capacityQuery?.eventId === event?.id
    && capacityQuery?.revision === availabilityRevision
    ? capacityQuery
    : null
  const isOwner = canManageEvent(auth, ownerAccess)
  const isEditing = isOwner && new URLSearchParams(location.search).get('edit') === '1'
  const currentRegistrationKey = `${event?.id ?? ''}:${auth.user?.id ?? 'anonymous'}`
  const registration = registrationState.eventKey === currentRegistrationKey
    ? registrationState
    : initialRegistrationState

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
    if (!event?.id) return undefined
    dispatchRegistration({ type: 'check/start', eventKey: currentRegistrationKey })
    if (auth.status !== 'authenticated') {
      dispatchRegistration({ type: 'check/complete', registration: null })
      return () => { active = false }
    }
    findMyEventRegistration(event.id)
      .then((result) => {
        if (active) dispatchRegistration({ type: 'check/complete', registration: result })
      })
      .catch(() => {
        if (active) dispatchRegistration({ type: 'check/failure' })
      })
    return () => { active = false }
  }, [auth.status, auth.user?.id, currentRegistrationKey, event?.id, registrationRevision])

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
      navigate(getEventEditorLocation(location.pathname, location.search, false), { replace: true })
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

  function closeEventEditor() {
    navigate(getEventEditorLocation(location.pathname, location.search, false), { replace: true })
    setEventAction({ status: 'idle', error: null })
  }

  async function handleRegistration() {
    if (registrationRequest.current || registration.status === 'loading') return
    if (auth.status !== 'authenticated') {
      navigate('/login', { state: { from: `${location.pathname}${location.search}` } })
      return
    }
    registrationRequest.current = true
    dispatchRegistration({ type: 'register/start', eventKey: currentRegistrationKey })
    try {
      await registerForEvent(event.id)
      setAvailabilityRevision((revision) => revision + 1)
      dispatchRegistration({ type: 'register/success', eventKey: currentRegistrationKey })
    } catch (requestError) {
      if (requestError.code === 'duplicate_registration') {
        dispatchRegistration({ type: 'register/duplicate', eventKey: currentRegistrationKey })
      } else {
        dispatchRegistration({ type: 'register/failure', error: requestError, eventKey: currentRegistrationKey })
      }
    } finally {
      registrationRequest.current = false
    }
  }

  async function handleCancelRegistration() {
    if (registrationRequest.current || !registration.registered) return
    if (!window.confirm(`¿Cancelar tu inscripción a “${event.title}”? La plaza podría quedar disponible para otra persona.`)) return
    registrationRequest.current = true
    dispatchRegistration({ type: 'cancel/start', eventKey: currentRegistrationKey })
    try {
      await cancelMyEventRegistration(event.id)
      setAvailabilityRevision((revision) => revision + 1)
      dispatchRegistration({ type: 'cancel/success', eventKey: currentRegistrationKey })
    } catch (requestError) {
      dispatchRegistration({ type: 'cancel/failure', error: requestError, eventKey: currentRegistrationKey })
    } finally {
      registrationRequest.current = false
    }
  }

  async function handleSaveSession(values) {
    if (sessionRequest.current) return
    sessionRequest.current = true
    setSessionAction({ status: 'saving', error: null, deletingId: null })
    try {
      if (sessionEditor) {
        await updateEventSession(event.id, sessionEditor.id, values)
      } else {
        await createEventSession(event.id, values)
      }
      setSessionEditor(undefined)
      setAvailabilityRevision((revision) => revision + 1)
      await loadEventSessions(event.id)
      setSessionAction({ status: 'saved', error: null, deletingId: null })
    } catch (requestError) {
      setSessionAction({ status: 'error', error: requestError, deletingId: null })
    } finally {
      sessionRequest.current = false
    }
  }

  async function handleDeleteSession(session) {
    if (sessionRequest.current) return
    if (!window.confirm(`¿Eliminar la sesión “${session.title}”? Esta acción no se puede deshacer.`)) return
    sessionRequest.current = true
    setSessionAction({ status: 'deleting', error: null, deletingId: session.id })
    try {
      await deleteEventSession(event.id, session.id)
      setAvailabilityRevision((revision) => revision + 1)
      await loadEventSessions(event.id)
      setSessionAction({ status: 'saved', error: null, deletingId: null })
    } catch (requestError) {
      setSessionAction({ status: 'error', error: requestError, deletingId: null })
    } finally {
      sessionRequest.current = false
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
          {isOwner && (
            <section aria-label="Administrar evento" className="event-management">
              {!isEditing && (
                <div className="button-row event-management-actions">
                  <button
                    className="button button-secondary"
                    disabled={eventAction.status === 'deleting'}
                    onClick={() => {
                      setEventAction({ status: 'idle', error: null })
                      navigate(getEventEditorLocation(location.pathname, location.search, true))
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
              {isEditing && (
                <EditorModal artworkTitle={event.title} onClose={closeEventEditor} title="Editar evento">
                  <EventForm
                    error={eventAction.error}
                    event={event}
                    isSubmitting={eventAction.status === 'saving'}
                    onCancel={closeEventEditor}
                    onSubmit={handleSaveEvent}
                  />
                </EditorModal>
              )}
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
              <RegistrationActions
                authStatus={auth.status}
                canRegister={canRegister}
                onCancel={handleCancelRegistration}
                onRegister={handleRegistration}
                registration={registration}
              />
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
              {registration.status === 'checking' && auth.status === 'authenticated' && <p className="event-neutral-note">Consultando tu inscripción…</p>}
              {registration.status === 'check-error' && (
                <div>
                  <p className="event-neutral-note">No pudimos consultar tu inscripción. Inténtalo de nuevo antes de continuar.</p>
                  <button className="button button-secondary" onClick={() => setRegistrationRevision((revision) => revision + 1)} type="button">Volver a consultar</button>
                </div>
              )}
            </div>
          )}
          {!canRegister && !registration.registered && <p className="event-neutral-note">Este evento no está aceptando inscripciones.</p>}
        </div>
      </article>

      <section aria-labelledby="sessions-heading" className="event-sessions-section">
        <header>
          <div><p className="eyebrow">La agenda</p><h2 id="sessions-heading">Sesiones del evento</h2></div>
          {isOwner && sessionEditor === undefined && (
            <button className="button button-secondary" disabled={sessionAction.status === 'saving' || sessionAction.status === 'deleting'} onClick={() => {
              setSessionAction({ status: 'idle', error: null, deletingId: null })
              setSessionEditor(null)
            }} type="button">Agregar sesión</button>
          )}
        </header>
        {isOwner && sessionEditor !== undefined && (
          <EditorModal
            artworkTitle={sessionEditor?.title || event.title}
            onClose={() => {
              setSessionEditor(undefined)
              setSessionAction({ status: 'idle', error: null, deletingId: null })
            }}
            title={sessionEditor ? 'Editar sesión' : 'Agregar sesión'}
          >
            <SessionForm
              error={sessionAction.status === 'error' ? sessionAction.error : null}
              event={event}
              isSubmitting={sessionAction.status === 'saving' || sessionAction.status === 'deleting'}
              onCancel={() => {
                setSessionEditor(undefined)
                setSessionAction({ status: 'idle', error: null, deletingId: null })
              }}
              onSubmit={handleSaveSession}
              session={sessionEditor || null}
            />
          </EditorModal>
        )}
        {sessionAction.status === 'saved' && <p className="feedback feedback-success" role="status">Los cambios de la sesión quedaron guardados.</p>}
        {sessionAction.status === 'error' && sessionEditor === undefined && <EventErrorMessage error={sessionAction.error} />}
        <SessionList
          busy={sessionAction.status === 'saving' || sessionAction.status === 'deleting'}
          canManage={isOwner}
          deletingId={sessionAction.deletingId}
          error={sessionsError}
          eventId={event.id}
          onDelete={handleDeleteSession}
          onEdit={(session) => {
            setSessionAction({ status: 'idle', error: null, deletingId: null })
            setSessionEditor(session)
          }}
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
