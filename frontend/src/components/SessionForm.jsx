/** Provide the existing API fields for creating and editing event sessions. */

import { useState } from 'react'
import { ErrorMessage } from './RequestFeedback.jsx'
import { toLocalDateTimeValue } from '../utils/eventForm.js'

/** Validate session values before submitting the backend's nested-session contract. */
export default function SessionForm({ event, session = null, error = null, isSubmitting = false, onCancel, onSubmit }) {
  const [validationError, setValidationError] = useState('')

  async function handleSubmit(submitEvent) {
    submitEvent.preventDefault()
    const values = new FormData(submitEvent.currentTarget)
    const startsAt = new Date(values.get('starts_at'))
    const endsAt = new Date(values.get('ends_at'))
    const eventStart = new Date(event.starts_at)
    const eventEnd = new Date(event.ends_at)
    const capacity = Number(values.get('capacity'))
    if (!values.get('title').trim() || !Number.isFinite(startsAt.getTime())
      || !Number.isFinite(endsAt.getTime()) || endsAt <= startsAt
      || startsAt < eventStart || endsAt > eventEnd
      || !Number.isInteger(capacity) || capacity < 1) {
      setValidationError('Revisa el título, las fechas dentro del evento y la capacidad de la sesión.')
      return
    }
    setValidationError('')
    await onSubmit({
      title: values.get('title').trim(),
      description: values.get('description').trim() || null,
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
      capacity,
      speaker_ids: session?.speaker_ids || [],
      ...(session ? { version: session.version } : {}),
    })
  }

  return (
    <form className="app-form session-form" noValidate onSubmit={handleSubmit}>
      {error && <ErrorMessage error={error} />}
      {validationError && <p className="field-error" role="alert">{validationError}</p>}
      <fieldset className="editor-form-group">
        <legend>Detalles de la sesión</legend>
        <div className="editor-form-grid">
          <label className="editor-form-field-full" htmlFor="session-title">Nombre de la sesión
            <input autoComplete="off" defaultValue={session?.title || ''} id="session-title" maxLength="200" name="title" required />
          </label>
          <label className="editor-form-field-full" htmlFor="session-description">Descripción
            <textarea defaultValue={session?.description || ''} id="session-description" name="description" rows="3" />
          </label>
          <label htmlFor="session-starts-at">Inicio
            <input defaultValue={session ? toLocalDateTimeValue(session.starts_at) : toLocalDateTimeValue(event.starts_at)} id="session-starts-at" name="starts_at" required type="datetime-local" />
          </label>
          <label htmlFor="session-ends-at">Fin
            <input defaultValue={session ? toLocalDateTimeValue(session.ends_at) : toLocalDateTimeValue(event.ends_at)} id="session-ends-at" name="ends_at" required type="datetime-local" />
          </label>
          <label htmlFor="session-capacity">Capacidad
            <input defaultValue={session?.capacity ?? event.capacity} id="session-capacity" min="1" name="capacity" required type="number" />
          </label>
        </div>
      </fieldset>
      <div className="button-row event-form-actions">
        <button className="button button-primary" disabled={isSubmitting} type="submit">
          {isSubmitting ? 'Guardando…' : session ? 'Guardar sesión' : 'Agregar sesión'}
        </button>
        <button className="button button-secondary" disabled={isSubmitting} onClick={onCancel} type="button">Cancelar</button>
      </div>
    </form>
  )
}
