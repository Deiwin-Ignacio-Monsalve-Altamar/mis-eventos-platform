/** Validate and normalize event form values for the backend event contract. */

const EVENT_STATUSES = new Set(['draft', 'published', 'cancelled', 'completed'])

/** Return a local datetime input value for an API timestamp. */
export function toLocalDateTimeValue(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (part) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** Convert local input time to the timezone-aware ISO value required by Flask. */
function toUtcIso(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

/** Validate event fields and return either a backend payload or field errors. */
export function validateEventForm(values) {
  const errors = {}
  const title = String(values.title ?? '').trim()
  const description = String(values.description ?? '').trim()
  const location = String(values.location ?? '').trim()
  const startsAt = toUtcIso(values.starts_at)
  const endsAt = toUtcIso(values.ends_at)
  const capacity = Number(values.capacity)
  const status = String(values.status ?? '')

  if (!title || Array.from(title).length > 200) {
    errors.title = 'Escribe un nombre de entre 1 y 200 caracteres.'
  }
  if (Array.from(location).length > 255) {
    errors.location = 'El lugar no puede superar los 255 caracteres.'
  }
  if (!startsAt) errors.starts_at = 'Ingresa una fecha y hora de inicio válidas.'
  if (!endsAt) errors.ends_at = 'Ingresa una fecha y hora de finalización válidas.'
  if (startsAt && endsAt && new Date(endsAt) <= new Date(startsAt)) {
    errors.ends_at = 'La finalización debe ser posterior al inicio.'
  }
  if (!Number.isInteger(capacity) || capacity < 1) {
    errors.capacity = 'La capacidad debe ser un número entero mayor que cero.'
  }
  if (!EVENT_STATUSES.has(status)) errors.status = 'Selecciona un estado válido.'

  if (Object.keys(errors).length > 0) return { errors, payload: null }
  return {
    errors,
    payload: {
      title,
      description: description || null,
      location: location || null,
      starts_at: startsAt,
      ends_at: endsAt,
      capacity,
      status,
    },
  }
}
