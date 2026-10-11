/** Show platform-wide administration analytics from protected aggregate data. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAdminDashboard } from '../api/admin.js'
import ProfileBarChart from '../components/ProfileBarChart.jsx'
import ProfileHero from '../components/ProfileHero.jsx'
import ProfileMetricGrid from '../components/ProfileMetricGrid.jsx'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render administration totals, trends, and operational organizer activity. */
export default function AdminProfile({ user }) {
  const { clearAuthentication } = useAppState()
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    getAdminDashboard().then((data) => {
      if (active) setState({ data, error: null, loading: false })
    }).catch((error) => {
      if (!active) return
      if (error.status === 401) clearAuthentication()
      setState({ data: null, error, loading: false })
    })
    return () => { active = false }
  }, [clearAuthentication, retry])

  const dashboard = state.data
  const summary = dashboard?.summary
  const months = (values = []) => values.map(({ month, count }) => ({
    label: new Intl.DateTimeFormat('es', { month: 'short', year: '2-digit', timeZone: 'UTC' })
      .format(new Date(`${month}-02T00:00:00Z`)),
    value: count,
  }))

  return (
    <div className="profile-page role-profile admin-profile">
      <ProfileHero eyebrow="Centro de administración" user={user} description="Supervisa la actividad de Mis Eventos y gestiona el acceso de organizadores." />
      <section aria-labelledby="admin-overview-heading" className="profile-activity">
        <div className="profile-section-heading">
          <div><p className="eyebrow">Vista general</p><h2 id="admin-overview-heading">Actividad de la plataforma</h2></div>
          <Link className="button button-primary" to="/admin/users">Administrar usuarios</Link>
        </div>
        {state.loading && <LoadingMessage>Cargando indicadores de la plataforma…</LoadingMessage>}
        {state.error && <><ErrorMessage error={state.error} /><button className="button button-secondary" onClick={() => setRetry((current) => current + 1)} type="button">Intentar de nuevo</button></>}
        {summary && <>
          {summary.users.total + summary.events.total + summary.registrations.total === 0
            ? <EmptyMessage>Aún no hay actividad registrada para mostrar.</EmptyMessage>
            : <>
              <ProfileMetricGrid label="Indicadores principales" metrics={[
                { label: 'Usuarios', value: summary.users.total },
                { label: 'Asistentes', value: summary.users.role_counts.ATTENDEE },
                { label: 'Organizadores', value: summary.users.role_counts.ORGANIZER },
                { label: 'Administradores', value: summary.users.role_counts.ADMIN },
                { label: 'Eventos creados', value: summary.events.total },
                { label: 'Próximos', value: summary.events.upcoming },
                { label: 'En curso', value: summary.events.active },
                { label: 'Finalizados', value: summary.events.finished },
                { label: 'Inscripciones activas', value: summary.registrations.active },
              ]} />
              <div className="profile-chart-grid">
                <ProfileBarChart label="Creación de eventos por mes" title="Eventos creados · últimos seis meses" items={months(dashboard.event_creation_by_month)} />
                <ProfileBarChart label="Inscripciones por mes" title="Inscripciones · últimos seis meses" items={months(dashboard.registration_activity_by_month)} />
                <ProfileBarChart label="Eventos por estado" title="Eventos por estado" items={Object.entries(summary.events.status_counts).map(([status, value]) => ({ label: EVENT_STATUS_LABELS[status] || status, value }))} />
              </div>
              <section aria-labelledby="organizer-activity-heading" className="organizer-activity-section">
                <div><p className="eyebrow">Operación</p><h3 id="organizer-activity-heading">Actividad de organizadores</h3>
                  <p>Eventos creados e inscripciones activas asociadas.</p></div>
                {dashboard.organizer_activity.length === 0
                  ? <EmptyMessage>Aún no hay organizadores registrados.</EmptyMessage>
                  : <div className="organizer-activity-list">{dashboard.organizer_activity.map((organizer) => (
                    <article className="organizer-activity-row" key={organizer.user_id}>
                      <strong>{organizer.name}</strong>
                      <span>{organizer.event_count} {organizer.event_count === 1 ? 'evento' : 'eventos'}</span>
                      <span>{organizer.active_registrations} inscripciones activas</span>
                    </article>
                  ))}</div>}
              </section>
            </>}
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
