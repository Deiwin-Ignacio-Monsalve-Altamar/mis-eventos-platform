/** Show owner-scoped event activity and management indicators for organizers. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMyEventMetrics } from '../api/events.js'
import EventArtwork from '../components/EventArtwork.jsx'
import ProfileBarChart from '../components/ProfileBarChart.jsx'
import ProfileHero from '../components/ProfileHero.jsx'
import ProfileMetricGrid from '../components/ProfileMetricGrid.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'
import { formatEventDate, getEventStatusLabel } from '../utils/eventPresentation.js'

/** Render only the authenticated organizer's real event and enrollment metrics. */
export default function OrganizerProfile({ user }) {
  const { clearAuthentication } = useAppState()
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    getMyEventMetrics().then((data) => {
      if (active) setState({ data, error: null, loading: false })
    }).catch((error) => {
      if (!active) return
      if (error.status === 401) clearAuthentication()
      setState({ data: null, error, loading: false })
    })
    return () => { active = false }
  }, [clearAuthentication, retry, user.id])

  const summary = state.data?.summary
  return (
    <div className="profile-page role-profile organizer-profile">
      <ProfileHero eyebrow="Espacio de organización" user={user} description="Administra tus eventos y consulta la actividad de las personas inscritas." />
      <section aria-labelledby="organizer-overview-heading" className="profile-activity">
        <div className="profile-section-heading">
          <div><p className="eyebrow">Tus eventos</p><h2 id="organizer-overview-heading">Resumen de gestión</h2></div>
          <div className="button-row"><Link className="button button-primary" to="/events/new">Crear evento</Link><Link className="button button-secondary" to="/my-events">Ver todos mis eventos</Link></div>
        </div>
        {state.loading && <LoadingMessage>Cargando tus indicadores…</LoadingMessage>}
        {state.error && <><ErrorMessage error={state.error} /><button className="button button-secondary" onClick={() => setRetry((current) => current + 1)} type="button">Intentar de nuevo</button></>}
        {summary && <>
          <ProfileMetricGrid label="Indicadores de gestión" metrics={[
            { label: 'Eventos creados', value: summary.total_events },
            { label: 'Próximos', value: summary.upcoming_events },
            { label: 'En curso', value: summary.active_events },
            { label: 'Finalizados', value: summary.finished_events },
            { label: 'Cancelados', value: summary.cancelled_events },
            { label: 'Inscripciones activas', value: summary.active_registrations },
          ]} />
          <ProfileBarChart label="Eventos propios por estado" title="Estado de tus eventos" items={Object.entries(summary.status_counts).map(([status, value]) => ({ label: EVENT_STATUS_LABELS[status] || status, value }))} />
          <section aria-labelledby="organizer-event-list-heading" className="organizer-owned-section">
            <div className="profile-section-heading"><div><p className="eyebrow">Seguimiento</p><h3 id="organizer-event-list-heading">Eventos próximos y gestionados</h3></div></div>
            {state.data.events.length === 0
              ? <div className="profile-empty-state"><EmptyMessage>Aún no has creado eventos.</EmptyMessage><Link className="button button-primary" to="/events/new">Crear tu primer evento</Link></div>
              : <div className="profile-owned-events">{state.data.events.map((event) => {
                const occupancy = event.capacity ? Math.min(100, Math.round(event.active_registrations * 100 / event.capacity)) : null
                return <article className="profile-owned-event organizer-owned-event" key={event.id}>
                  <EventArtwork title={event.title} />
                  <div className="organizer-event-info">
                    <span className={`status-badge status-${event.status}`}>{getEventStatusLabel(event.status)}</span>
                    <h4><Link to={`/events/${event.id}`}>{event.title}</Link></h4>
                    <p><time dateTime={event.starts_at}>{formatEventDate(event.starts_at, 'medium')}</time></p>
                    <div className="organizer-event-stats"><span>{event.session_count} sesiones</span><span>{event.active_registrations} inscripciones activas</span><span>{event.available_seats} cupos libres</span></div>
                    {occupancy !== null && <div aria-label={`Ocupación de ${event.title}: ${occupancy}%`} aria-valuemax="100" aria-valuemin="0" aria-valuenow={occupancy} className="occupancy-track" role="progressbar"><span style={{ width: `${occupancy}%` }} /></div>}
                  </div>
                  <Link className="text-link" to={`/events/${event.id}?edit=1`}>Gestionar</Link>
                </article>
              })}</div>}
          </section>
        </>}
      </section>
    </div>
  )
}

const EVENT_STATUS_LABELS = {
  draft: 'Borrador',
  published: 'Publicado',
  cancelled: 'Cancelado',
  completed: 'Finalizado',
}
