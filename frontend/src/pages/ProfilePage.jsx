/** Show the current profile loaded from the authenticated API endpoint. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listMyRegistrations } from '../api/registrations.js'
import AuthErrorMessage from '../components/AuthErrorMessage.jsx'
import { EmptyMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render the user's public identity and API-backed event registrations. */
export default function ProfilePage() {
  const { state } = useAppState()
  const { auth } = state
  const [registrationQuery, setRegistrationQuery] = useState(null)
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
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
        </div>
        <p className="profile-welcome-note">Los buenos momentos empiezan cuando hacemos espacio para encontrarnos.</p>
      </header>

      <section aria-labelledby="registrations-heading" className="profile-registrations">
        <div className="profile-section-heading">
          <div>
            <p className="eyebrow">Tu vida de eventos</p>
            <h2 id="registrations-heading">Mis inscripciones</h2>
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
                  </div>
                  <span className={`registration-status status-${registration.status}`}>
                    {registration.status === 'registered' ? 'Inscrito' : 'Cancelada'}
                  </span>
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
          </>
        )}
      </section>
    </div>
  )
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
