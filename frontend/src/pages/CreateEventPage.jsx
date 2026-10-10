/** Create an event through the authenticated event-management API. */

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import EventForm from '../components/EventForm.jsx'
import { ErrorMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Require a signed-in user and create an event with normalized form values. */
export default function CreateEventPage() {
  const { state, submitEvent } = useAppState()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(values) {
    setError(null)
    setIsSubmitting(true)
    try {
      const createdEvent = await submitEvent(values)
      navigate(`/events/${createdEvent.id}`, { replace: true })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (state.auth.status === 'loading') {
    return <p aria-live="polite">Estamos verificando tu sesión…</p>
  }
  if (state.auth.status !== 'authenticated') {
    return (
      <section aria-labelledby="create-event-access-heading" className="content-panel create-event-access">
        <p className="eyebrow">Comparte algo que valga la pena vivir</p>
        <h1 id="create-event-access-heading">Inicia sesión para crear un evento</h1>
        <p>Necesitas una cuenta para organizar un evento. Inicia sesión o crea una cuenta para continuar.</p>
        {state.auth.status === 'error' && <ErrorMessage error={state.auth.error} />}
        <div className="button-row">
          <Link className="button button-primary" state={{ from: `${location.pathname}${location.search}` }} to="/login">Iniciar sesión</Link>
          <Link className="button button-secondary" state={{ from: `${location.pathname}${location.search}` }} to="/register">Crear una cuenta</Link>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="create-event-heading" className="form-panel">
      <p className="eyebrow">Comparte algo que valga la pena vivir</p>
      <h1 id="create-event-heading">Crear evento</h1>
      {error && <ErrorMessage error={error} />}
      <EventForm error={null} isSubmitting={isSubmitting} onSubmit={handleSubmit} />
      <p className="form-footnote"><Link to="/events">Volver al catálogo</Link></p>
    </section>
  )
}
