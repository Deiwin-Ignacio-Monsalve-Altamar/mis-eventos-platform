/** Provide a small event creation form backed by the documented event API. */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ErrorMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Validate basic required fields and submit an event for the current user. */
export default function CreateEventPage() {
  const { state, submitEvent } = useAppState()
  const navigate = useNavigate()
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError(null)
    setSubmitting(true)
    const formData = new FormData(event.currentTarget)
    try {
      const newEvent = await submitEvent({
        title: formData.get('title'),
        description: formData.get('description') || null,
        location: formData.get('location') || null,
        starts_at: toUtc(formData.get('starts_at')),
        ends_at: toUtc(formData.get('ends_at')),
        capacity: Number(formData.get('capacity')),
        status: formData.get('status'),
      })
      if (!newEvent) {
        setFormError(state.eventCreation.error)
        return
      }
      navigate(`/events/${newEvent.id}`)
    } catch (error) {
      setFormError(error)
    } finally {
      setSubmitting(false)
    }
  }

  if (state.auth.status === 'loading') {
    return <p aria-live="polite">Estamos verificando tu sesión…</p>
  }
  if (state.auth.status !== 'authenticated') {
    return (
      <section className="content-panel">
        <h1>Inicia sesión para crear un evento</h1>
        <p>La creación de eventos está disponible para cuentas autenticadas.</p>
        {state.auth.status === 'error' && <ErrorMessage error={state.auth.error} />}
        <Link className="button button-primary" to="/login">Iniciar sesión</Link>
      </section>
    )
  }

  return (
    <section className="form-panel">
      <p className="eyebrow">Comparte algo que valga la pena vivir</p>
      <h1>Crear evento</h1>
      <ErrorMessage error={formError || state.eventCreation.error} />
      <form className="app-form" onSubmit={handleSubmit}>
        <label>
          Nombre del evento
          <input autoComplete="off" maxLength="200" name="title" required />
        </label>
        <label>
          Descripción
          <textarea name="description" rows="4" />
        </label>
        <label>
          Lugar
          <input maxLength="255" name="location" />
        </label>
        <div className="form-columns">
          <label>
            Fecha y hora de inicio
            <input name="starts_at" required type="datetime-local" />
          </label>
          <label>
            Fecha y hora de finalización
            <input name="ends_at" required type="datetime-local" />
          </label>
        </div>
        <div className="form-columns">
          <label>
            Capacidad
            <input min="1" name="capacity" required type="number" />
          </label>
          <label>
            Estado
            <select defaultValue="draft" name="status">
              <option value="draft">Borrador</option>
              <option value="published">Publicado</option>
            </select>
          </label>
        </div>
        <button className="button button-primary" disabled={submitting} type="submit">
          {submitting ? 'Creando…' : 'Crear evento'}
        </button>
      </form>
    </section>
  )
}

/** Convert a local date-time input to the ISO 8601 UTC form expected by the API. */
function toUtc(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    throw new Error('Ingresa una fecha y hora válidas.')
  }
  return date.toISOString()
}
