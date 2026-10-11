/** Focus the attendee profile on their registrations and available new events. */

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getRecommendedEvents } from '../api/events.js'
import { cancelMyEventRegistration, getMyRegistrationSummary, listMyRegistrations } from '../api/registrations.js'
import EventRecommendations from '../components/EventRecommendations.jsx'
import ProfileHero from '../components/ProfileHero.jsx'
import ProfileMetricGrid from '../components/ProfileMetricGrid.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import useAppState from '../state/useAppState.js'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

const PAGE_SIZE = 20

/** Render attendee-only registration history and live available-event recommendations. */
export default function AttendeeProfile({ user }) {
  const { clearAuthentication } = useAppState()
  const [searchParams, setSearchParams] = useSearchParams()
  const [summaryState, setSummaryState] = useState(null)
  const [registrationState, setRegistrationState] = useState(null)
  const [recommendationState, setRecommendationState] = useState(null)
  const [retry, setRetry] = useState(0)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState(null)
  const [busyEventId, setBusyEventId] = useState(null)
  const cancellationPending = useRef(false)
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const requestKey = `${user.id}:${page}:${retry}`
  const summary = summaryState?.key === `${user.id}:${retry}` ? summaryState.data : null
  const summaryError = summaryState?.key === `${user.id}:${retry}` ? summaryState.error : null
  const registrations = registrationState?.key === requestKey ? registrationState.data : null
  const registrationError = registrationState?.key === requestKey ? registrationState.error : null
  const recommendations = recommendationState?.key === `${user.id}:${retry}` ? recommendationState.data : null
  const recommendationError = recommendationState?.key === `${user.id}:${retry}` ? recommendationState.error : null

  useEffect(() => {
    let active = true
    getMyRegistrationSummary().then((data) => {
      if (active) setSummaryState({ key: `${user.id}:${retry}`, data, error: null })
    }).catch((error) => {
      if (!active) return
      if (error.status === 401) clearAuthentication()
      setSummaryState({ key: `${user.id}:${retry}`, data: null, error })
    })
    getRecommendedEvents().then((data) => {
      if (active) setRecommendationState({ key: `${user.id}:${retry}`, data, error: null })
    }).catch((error) => {
      if (!active) return
      if (error.status === 401) clearAuthentication()
      setRecommendationState({ key: `${user.id}:${retry}`, data: null, error })
    })
    return () => { active = false }
  }, [clearAuthentication, retry, user.id])

  useEffect(() => {
    let active = true
    listMyRegistrations({ page, pageSize: PAGE_SIZE }).then((data) => {
      if (active) setRegistrationState({ key: requestKey, data, error: null })
    }).catch((error) => {
      if (!active) return
      if (error.status === 401) clearAuthentication()
      setRegistrationState({ key: requestKey, data: null, error })
    })
    return () => { active = false }
  }, [clearAuthentication, page, requestKey])

  async function cancelRegistration(registration) {
    if (cancellationPending.current || registration.status !== 'registered') return
    if (!window.confirm(`¿Cancelar tu inscripción a “${registration.event.title}”? La plaza podría quedar disponible para otra persona.`)) return
    cancellationPending.current = true
    setBusyEventId(registration.event.id)
    setActionError(null)
    setNotice('')
    try {
      await cancelMyEventRegistration(registration.event.id)
      setNotice('Tu inscripción quedó cancelada.')
      setRetry((current) => current + 1)
    } catch (error) {
      if (error.status === 401) clearAuthentication()
      setActionError(error)
    } finally {
      cancellationPending.current = false
      setBusyEventId(null)
    }
  }

  const upcoming = registrations?.registrations.filter((registration) => (
    registration.status === 'registered'
    && registration.event.status !== 'cancelled'
    && registration.event.status !== 'completed'
    && isUpcoming(registration.event)
  )) || []
  const past = registrations?.registrations.filter((registration) => !upcoming.includes(registration)) || []

  return (
    <div className="profile-page role-profile attendee-profile">
      <ProfileHero eyebrow="Tu espacio de eventos" user={user} description="Encuentra tus próximas experiencias y descubre nuevos eventos para tu agenda." />
      <section aria-labelledby="attendee-overview-heading" className="profile-activity">
        <div className="profile-section-heading"><div><p className="eyebrow">Tu participación</p><h2 id="attendee-overview-heading">Mis inscripciones</h2></div><Link className="button button-secondary" to="/my-registrations">Ver todas</Link></div>
        {summary && <ProfileMetricGrid label="Resumen de inscripciones" metrics={[
          { label: 'Inscripciones', value: summary.total },
          { label: 'Activas', value: summary.active },
          { label: 'Próximas', value: summary.upcoming },
          { label: 'Eventos pasados', value: summary.past },
          { label: 'Canceladas', value: summary.cancelled },
        ]} />}
        {summaryError && <><ErrorMessage error={summaryError} /><button className="button button-secondary" onClick={() => setRetry((current) => current + 1)} type="button">Intentar de nuevo</button></>}
        {notice && <p aria-live="polite" className="feedback feedback-success" role="status">{notice}</p>}
        {actionError && <ErrorMessage error={actionError} />}
        {registrationError && <><ErrorMessage error={registrationError} /><button className="button button-secondary" onClick={() => setRetry((current) => current + 1)} type="button">Intentar de nuevo</button></>}
        {!registrations && !registrationError && <LoadingMessage>Cargando tus inscripciones…</LoadingMessage>}
        {registrations && registrations.registrations.length === 0 && <div className="profile-empty-state"><EmptyMessage>Aún no tienes inscripciones a eventos.</EmptyMessage><Link className="button button-primary" to="/events">Explorar eventos</Link></div>}
        {upcoming.length > 0 && <RegistrationSection busyEventId={busyEventId} onCancel={cancelRegistration} registrations={upcoming} title="Próximas experiencias" />}
        {past.length > 0 && <RegistrationSection busyEventId={busyEventId} onCancel={cancelRegistration} registrations={past} title="Historial de inscripciones" />}
        <PaginationControls disabled={!registrations || busyEventId !== null} itemLabel="inscripciones" onPageChange={(nextPage) => { const next = new URLSearchParams(searchParams); next.set('page', String(nextPage)); setSearchParams(next) }} pagination={registrations?.pagination} />
      </section>
      <EventRecommendations error={recommendationError} loading={!recommendations && !recommendationError} recommendations={recommendations} />
    </div>
  )
}

function isUpcoming(event) {
  return Date.parse(event.ends_at) > Date.now()
}

function RegistrationSection({ title, registrations, busyEventId, onCancel }) {
  return <section aria-label={title} className="attendee-registration-section">
    <h3>{title}</h3>
    <div className="attendee-registration-list">{registrations.map((registration) => (
      <article className="attendee-registration-card" key={registration.id}>
        <div><span className={`status-badge status-${registration.event.status}`}>{getEventStatusLabel(registration.event.status)}</span>
          <h4><Link to={`/events/${registration.event.id}`}>{registration.event.title}</Link></h4>
          <p><time dateTime={registration.event.starts_at}>{formatEventDate(registration.event.starts_at, 'medium')}</time></p>
          <p>{registration.event.location || 'Lugar por confirmar'}</p>
          {registration.status === 'registered' && registration.event.status === 'completed' && <p className="attendance-note">La inscripción no acredita asistencia presencial.</p>}
        </div>
        <div className="attendee-registration-actions"><span className={`registration-status status-${registration.status}`}>{registration.status === 'registered' ? 'Inscrito' : 'Cancelada'}</span>
          {registration.status === 'registered' && <button className="button button-secondary" disabled={busyEventId === registration.event.id} onClick={() => onCancel(registration)} type="button">{busyEventId === registration.event.id ? 'Cancelando…' : 'Cancelar inscripción'}</button>}
        </div>
      </article>
    ))}</div>
  </section>
}
