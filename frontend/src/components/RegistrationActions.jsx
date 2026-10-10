/** Render enrollment actions from the current persisted registration state. */

/** Show the action that matches enrollment status without masking success. */
export default function RegistrationActions({
  registration,
  canRegister,
  authStatus,
  onRegister,
  onCancel,
}) {
  if (registration.registered) {
    return (
      <button
        className="button button-secondary"
        disabled={registration.status === 'cancelling'}
        onClick={onCancel}
        type="button"
      >
        {registration.status === 'cancelling' ? 'Cancelando inscripción…' : 'Cancelar inscripción'}
      </button>
    )
  }

  if (!canRegister) return null

  return (
    <button
      aria-busy={registration.status === 'loading'}
      className="button button-primary"
      disabled={registration.status === 'loading' || registration.status === 'checking' || registration.status === 'check-error' || authStatus === 'loading'}
      onClick={onRegister}
      type="button"
    >
      {registration.status === 'loading' ? 'Inscribiéndote…' : 'Inscribirme'}
    </button>
  )
}
