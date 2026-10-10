/** Render exactly one status message for the current registration transition. */

/** Select the single user-facing notice associated with registration state. */
export default function RegistrationNotice({ registration }) {
  let message = ''
  if (registration.status === 'success') {
    message = 'Tu inscripción quedó confirmada.'
  } else if (registration.status === 'cancelled') {
    message = 'Cancelaste tu inscripción. La plaza quedó disponible si el evento admite nuevas inscripciones.'
  } else if (registration.status === 'duplicate') {
    message = 'Ya tienes una inscripción activa para este evento.'
  } else if (registration.registered && registration.status === 'idle') {
    message = 'Ya tienes una inscripción activa para este evento.'
  }

  return message
    ? <p className="feedback feedback-success" role="status">{message}</p>
    : null
}
