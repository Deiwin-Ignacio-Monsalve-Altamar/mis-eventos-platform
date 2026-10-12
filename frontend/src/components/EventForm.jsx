/** Render the shared create and edit form using the backend event fields. */

import { useEffect, useRef, useState } from 'react'
import { ErrorMessage } from './RequestFeedback.jsx'
import EventCover from './EventCover.jsx'
import { toLocalDateTimeValue, validateEventForm } from '../utils/eventForm.js'

const EVENT_STATUS_OPTIONS = [
  ['draft', 'Borrador'],
  ['published', 'Publicado'],
  ['cancelled', 'Cancelado'],
  ['completed', 'Finalizado'],
]
const MAX_IMAGE_COUNT = 10
const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const ACCEPTED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

/** Submit normalized values and expose accessible client/server validation. */
export default function EventForm({
  event = null,
  error = null,
  isSubmitting = false,
  onCancel,
  onSubmit,
}) {
  const [validationErrors, setValidationErrors] = useState({})
  const [selectedImages, setSelectedImages] = useState([])
  const [imageError, setImageError] = useState('')
  const selectedImagesRef = useRef(selectedImages)
  const isEditing = Boolean(event)
  const serverValidationErrors = getServerValidationErrors(error)
  const fieldErrors = { ...serverValidationErrors, ...validationErrors }

  useEffect(() => {
    selectedImagesRef.current = selectedImages
  }, [selectedImages])
  useEffect(() => () => selectedImagesRef.current.forEach((image) => URL.revokeObjectURL(image.preview)), [])

  async function handleSubmit(submitEvent) {
    submitEvent.preventDefault()
    const formData = new FormData(submitEvent.currentTarget)
    const result = validateEventForm(Object.fromEntries(formData.entries()))
    setValidationErrors(result.errors)
    if (!result.payload) return
    const action = submitEvent.nativeEvent.submitter?.value === 'publish' ? 'publish' : 'save'
    const payload = action === 'publish' ? { ...result.payload, status: 'published' } : result.payload
    await onSubmit(payload, selectedImages.map(({ file }) => file), action)
  }

  function handleImageSelection(changeEvent) {
    const files = Array.from(changeEvent.target.files || [])
    const total = selectedImages.length + files.length
    if (total > MAX_IMAGE_COUNT) {
      setImageError(`Puedes seleccionar hasta ${MAX_IMAGE_COUNT} imágenes.`)
      changeEvent.target.value = ''
      return
    }
    const invalidFile = files.find((file) => !ACCEPTED_IMAGE_TYPES.has(file.type) || file.size > MAX_IMAGE_SIZE)
    if (invalidFile) {
      setImageError('Selecciona imágenes JPEG, PNG o WebP de máximo 5 MB cada una.')
      changeEvent.target.value = ''
      return
    }
    setImageError('')
    setSelectedImages((current) => [...current, ...files.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
    }))])
    changeEvent.target.value = ''
  }

  function removeImage(index) {
    setSelectedImages((current) => {
      const removed = current[index]
      if (removed) URL.revokeObjectURL(removed.preview)
      return current.filter((_, imageIndex) => imageIndex !== index)
    })
  }

  function fieldProps(name) {
    return {
      'aria-describedby': fieldErrors[name] ? `${name}-error` : undefined,
      'aria-invalid': Boolean(fieldErrors[name]),
    }
  }

  return (
    <form className="app-form event-form" noValidate onSubmit={handleSubmit}>
      {error && <ErrorMessage error={error} />}
      {error?.code === 'validation_error' && error.message && (
        <p className="field-error" role="status">El servidor rechazó los cambios: {error.message}</p>
      )}
      {Object.keys(fieldErrors).length > 0 && (
        <p className="field-error" role="alert">Revisa los campos señalados antes de guardar.</p>
      )}
      <fieldset className="editor-form-group">
        <legend>Información del evento</legend>
        <div className="editor-form-grid">
          <label className="editor-form-field-full" htmlFor="event-title">
            Nombre del evento
            <input {...fieldProps('title')} autoComplete="off" id="event-title" maxLength="200" name="title" required defaultValue={event?.title || ''} />
            {fieldErrors.title && <span className="field-error" id="title-error">{fieldErrors.title}</span>}
          </label>
          <label className="editor-form-field-full" htmlFor="event-description">
            Descripción <span className="field-hint">Opcional</span>
            <textarea id="event-description" name="description" rows="4" defaultValue={event?.description || ''} />
          </label>
          <label className="editor-form-field-full" htmlFor="event-location">
            Lugar <span className="field-hint">Opcional; máximo 255 caracteres</span>
            <input {...fieldProps('location')} id="event-location" maxLength="255" name="location" defaultValue={event?.location || ''} />
            {fieldErrors.location && <span className="field-error" id="location-error">{fieldErrors.location}</span>}
          </label>
        </div>
      </fieldset>
      <fieldset className="editor-form-group">
        <legend>Fechas y capacidad</legend>
        <div className="editor-form-grid">
        <label htmlFor="event-starts-at">
          Fecha y hora de inicio
          <input {...fieldProps('starts_at')} id="event-starts-at" name="starts_at" required type="datetime-local" defaultValue={event ? toLocalDateTimeValue(event.starts_at) : ''} />
          {fieldErrors.starts_at && <span className="field-error" id="starts_at-error">{fieldErrors.starts_at}</span>}
        </label>
        <label htmlFor="event-ends-at">
          Fecha y hora de finalización
          <input {...fieldProps('ends_at')} id="event-ends-at" name="ends_at" required type="datetime-local" defaultValue={event ? toLocalDateTimeValue(event.ends_at) : ''} />
          {fieldErrors.ends_at && <span className="field-error" id="ends_at-error">{fieldErrors.ends_at}</span>}
        </label>
        <label htmlFor="event-capacity">
          Capacidad
          <input {...fieldProps('capacity')} id="event-capacity" min="1" name="capacity" required type="number" defaultValue={event?.capacity ?? ''} />
          {fieldErrors.capacity && <span className="field-error" id="capacity-error">{fieldErrors.capacity}</span>}
        </label>
        <label htmlFor="event-status">
          Estado
          <select {...fieldProps('status')} defaultValue={event?.status || 'draft'} id="event-status" name="status">
            {EVENT_STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {fieldErrors.status && <span className="field-error" id="status-error">{fieldErrors.status}</span>}
        </label>
        </div>
      </fieldset>
      <fieldset className="editor-form-group">
        <legend>Imágenes del evento <span className="field-hint">Opcional · hasta 10 imágenes, 5 MB cada una</span></legend>
        {isEditing && event.images?.length > 0 && selectedImages.length === 0 && (
          <div aria-label="Galería actual; se conservará si no seleccionas imágenes nuevas" className="event-current-images">
            <div>
              <h3>Portada actual</h3>
              <EventCover event={event} variant="editor" />
            </div>
            {event.images.some((image) => image.position !== 0) && (
              <div>
                <h3>Otras imágenes actuales</h3>
                <div className="event-image-grid event-image-grid-compact">
                  {[...event.images].filter((image) => image.position !== 0).sort((a, b) => a.position - b.position).map((image, index) => (
                    <img alt={`${event.title}, imagen ${index + 2}`} key={`${image.position}-${image.url}`} src={image.url} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <label className="editor-form-field-full" htmlFor="event-images">
          {isEditing ? 'Seleccionar imágenes para reemplazar la galería' : 'Seleccionar imágenes'}
          <input
            accept="image/jpeg,image/png,image/webp"
            id="event-images"
            multiple
            onChange={handleImageSelection}
            type="file"
          />
        </label>
        {imageError && <p className="field-error" role="alert">{imageError}</p>}
        {selectedImages.length > 0 && (
          <div aria-label="Previsualizaciones de imágenes seleccionadas" className="event-image-grid">
            {selectedImages.map(({ file, preview }, index) => (
              <figure key={`${file.name}-${index}`}>
                <img alt={`Previsualización: ${file.name}`} src={preview} />
                <figcaption>
                  <span>{file.name}</span>
                  <button aria-label={`Quitar ${file.name}`} className="button button-secondary" onClick={() => removeImage(index)} type="button">Quitar</button>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </fieldset>
      <div className="button-row event-form-actions">
        <button className="button button-primary" disabled={isSubmitting} type="submit">
          {isSubmitting ? 'Guardando…' : isEditing ? 'Guardar cambios' : 'Crear evento'}
        </button>
        {isEditing && event.status === 'draft' && (
          <button className="button button-secondary" disabled={isSubmitting} name="action" type="submit" value="publish">
            {isSubmitting ? 'Publicando…' : 'Publicar evento'}
          </button>
        )}
        {onCancel && <button className="button button-secondary" disabled={isSubmitting} onClick={onCancel} type="button">Cancelar</button>}
      </div>
    </form>
  )
}

/** Attach backend validation messages to fields when its existing message names one. */
function getServerValidationErrors(error) {
  if (error?.code !== 'validation_error' || !error.message) return {}
  const message = error.message
  const normalized = message.toLowerCase()
  const field = ['title', 'description', 'location', 'starts_at', 'ends_at', 'capacity', 'status']
    .find((name) => normalized.startsWith(`${name} `))
  if (field) return { [field]: message }
  if (normalized.startsWith('capacity cannot be lower')) return { capacity: message }
  if (normalized.startsWith('the event schedule cannot exclude')) return { starts_at: message, ends_at: message }
  return {}
}
