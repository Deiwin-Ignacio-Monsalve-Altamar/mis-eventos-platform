/** Present event API errors in Spanish without exposing internal diagnostics. */

const EVENT_ERROR_MESSAGES = {
  authentication_required: 'Inicia sesión para continuar.',
  capacity_exceeded: 'Ya no quedan cupos disponibles para este evento.',
  duplicate_registration: 'Ya tienes una inscripción activa para este evento.',
  event_unavailable: 'Este evento no admite nuevas inscripciones.',
  network_error: 'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
  not_found: 'No encontramos este evento. Puede que ya no esté disponible.',
  validation_error: 'No pudimos completar la solicitud. Revisa la información e inténtalo de nuevo.',
}

/** Render a safe, localized API error as an accessible alert. */
export default function EventErrorMessage({ error }) {
  if (!error) return null
  const message = EVENT_ERROR_MESSAGES[error.code]
    || 'Ocurrió un problema al cargar la información. Inténtalo de nuevo.'

  return (
    <div aria-live="assertive" className="feedback feedback-error" role="alert">
      <p>{message}</p>
    </div>
  )
}
