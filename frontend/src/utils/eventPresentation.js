/** Format event data for consistent Spanish presentation across event screens. */

const EVENT_STATUS_LABELS = {
  cancelled: 'Cancelado',
  completed: 'Finalizado',
  draft: 'Borrador',
  published: 'Publicado',
}

/** Return a Spanish label for a known event status. */
export function getEventStatusLabel(status) {
  return EVENT_STATUS_LABELS[status] || 'Estado no disponible'
}

/** Format an ISO timestamp in Spanish, preserving invalid source text safely. */
export function formatEventDate(value, dateStyle = 'full') {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'Fecha por confirmar'
  return new Intl.DateTimeFormat('es', { dateStyle, timeStyle: 'short' }).format(date)
}

/** Sort sessions by start timestamp and then ID for a stable tie order. */
export function sortSessions(sessions) {
  return [...sessions].sort((left, right) => {
    const startDifference = Date.parse(left.starts_at) - Date.parse(right.starts_at)
    if (Number.isFinite(startDifference) && startDifference !== 0) return startDifference
    return left.id - right.id
  })
}

/** Check the same public registration window enforced by the backend. */
export function isEventOpenForRegistration(event, now = Date.now()) {
  const startsAt = Date.parse(event.starts_at)
  return event.status === 'published' && Number.isFinite(startsAt) && startsAt > now
}

/** Describe availability only from the session capacity response and request state. */
export function getSessionAvailability(occupancy, unavailable, fallbackCapacity) {
  if (unavailable) {
    return {
      label: 'Disponibilidad desconocida',
      detail: `Capacidad máxima: ${fallbackCapacity}`,
      tone: 'unknown',
    }
  }
  if (!occupancy) {
    return { label: 'Consultando disponibilidad…', detail: null, tone: 'pending' }
  }
  if (occupancy.available <= 0) {
    return {
      label: 'Sin cupos',
      detail: `0 cupos disponibles de ${occupancy.capacity}`,
      tone: 'full',
    }
  }

  return {
    label: 'Disponible',
    detail: `${occupancy.available} ${occupancy.available === 1 ? 'cupo disponible' : 'cupos disponibles'} de ${occupancy.capacity}`,
    tone: 'available',
  }
}
