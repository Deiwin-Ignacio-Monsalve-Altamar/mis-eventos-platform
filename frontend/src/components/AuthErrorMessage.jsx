/** Present authentication and account errors with clear Spanish copy. */

const AUTH_ERROR_MESSAGES = {
  account_exists: 'Ya existe una cuenta con ese correo electrónico.',
  authentication_required: 'Tu sesión no está disponible. Inicia sesión para continuar.',
  authentication_unavailable: 'El inicio de sesión no está disponible en este momento. Inténtalo más tarde.',
  invalid_credentials: 'El correo electrónico o la contraseña no son correctos.',
  invalid_token: 'Tu sesión no es válida. Inicia sesión nuevamente.',
  network_error: 'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
  validation_error: 'Revisa los datos ingresados e inténtalo de nuevo.',
}

/** Render a localized message without exposing backend diagnostics to users. */
export default function AuthErrorMessage({ error }) {
  if (!error) return null
  const message = AUTH_ERROR_MESSAGES[error.code]
    || 'No pudimos completar la solicitud. Inténtalo de nuevo.'

  return (
    <div aria-live="assertive" className="feedback feedback-error" role="alert">
      <p>{message}</p>
    </div>
  )
}
