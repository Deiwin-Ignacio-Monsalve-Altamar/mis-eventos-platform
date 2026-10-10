/** Render the shared create and edit form using the backend event fields. */

import { useState } from 'react'
import { ErrorMessage } from './RequestFeedback.jsx'
import { toLocalDateTimeValue, validateEventForm } from '../utils/eventForm.js'

const EVENT_STATUS_OPTIONS = [
  ['draft', 'Borrador'],
  ['published', 'Publicado'],
  ['cancelled', 'Cancelado'],
  ['completed', 'Finalizado'],
]

/** Submit normalized values and expose accessible client/server validation. */
export default function EventForm({
  event = null,
  error = null,
  isSubmitting = false,
  onCancel,
  onSubmit,
}) {
  const [validationErrors, setValidationErrors] = useState({})
  const isEditing = Boolean(event)

  async function handleSubmit(submitEvent) {
    submitEvent.preventDefault()
    const formData = new FormData(submitEvent.currentTarget)
    const result = validateEventForm(Object.fromEntries(formData.entries()))
    setValidationErrors(result.errors)
    if (!result.payload) return
    await onSubmit(result.payload)
  }

  function fieldProps(name) {
    return {
      'aria-describedby': validationErrors[name] ? `${name}-error` : undefined,
      'aria-invalid': Boolean(validationErrors[name]),
    }
  }

  return (
    <form className="app-form event-form" noValidate onSubmit={handleSubmit}>
      {error && <ErrorMessage error={error} />}
      {Object.keys(validationErrors).length > 0 && (
        <p className="field-error" role="alert">Revisa los campos señalados antes de guardar.</p>
      )}
      <label htmlFor="event-title">
        Nombre del evento
        <input {...fieldProps('title')} autoComplete="off" id="event-title" maxLength="200" name="title" required defaultValue={event?.title || ''} />
        {validationErrors.title && <span className="field-error" id="title-error">{validationErrors.title}</span>}
      </label>
      <label htmlFor="event-description">
        Descripción <span className="field-hint">Opcional</span>
        <textarea id="event-description" name="description" rows="4" defaultValue={event?.description || ''} />
      </label>
      <label htmlFor="event-location">
        Lugar <span className="field-hint">Opcional; máximo 255 caracteres</span>
        <input {...fieldProps('location')} id="event-location" maxLength="255" name="location" defaultValue={event?.location || ''} />
        {validationErrors.location && <span className="field-error" id="location-error">{validationErrors.location}</span>}
      </label>
      <div className="form-columns">
        <label htmlFor="event-starts-at">
          Fecha y hora de inicio
          <input {...fieldProps('starts_at')} id="event-starts-at" name="starts_at" required type="datetime-local" defaultValue={event ? toLocalDateTimeValue(event.starts_at) : ''} />
          {validationErrors.starts_at && <span className="field-error" id="starts_at-error">{validationErrors.starts_at}</span>}
        </label>
        <label htmlFor="event-ends-at">
          Fecha y hora de finalización
          <input {...fieldProps('ends_at')} id="event-ends-at" name="ends_at" required type="datetime-local" defaultValue={event ? toLocalDateTimeValue(event.ends_at) : ''} />
          {validationErrors.ends_at && <span className="field-error" id="ends_at-error">{validationErrors.ends_at}</span>}
        </label>
      </div>
      <div className="form-columns">
        <label htmlFor="event-capacity">
          Capacidad
          <input {...fieldProps('capacity')} id="event-capacity" min="1" name="capacity" required type="number" defaultValue={event?.capacity ?? ''} />
          {validationErrors.capacity && <span className="field-error" id="capacity-error">{validationErrors.capacity}</span>}
        </label>
        <label htmlFor="event-status">
          Estado
          <select {...fieldProps('status')} defaultValue={event?.status || 'draft'} id="event-status" name="status">
            {EVENT_STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {validationErrors.status && <span className="field-error" id="status-error">{validationErrors.status}</span>}
        </label>
      </div>
      <div className="button-row event-form-actions">
        <button className="button button-primary" disabled={isSubmitting} type="submit">
          {isSubmitting ? 'Guardando…' : isEditing ? 'Guardar cambios' : 'Crear evento'}
        </button>
        {onCancel && <button className="button button-secondary" disabled={isSubmitting} onClick={onCancel} type="button">Cancelar</button>}
      </div>
    </form>
  )
}
