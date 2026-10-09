/** Render consistent loading, error, and empty-state feedback for pages. */

const ERROR_MESSAGES = {
  authentication_required: 'Inicia sesión para continuar.',
  authentication_unavailable: 'La autenticación no está disponible en este momento.',
  concurrency_conflict: 'El evento cambió mientras lo editabas. Actualiza la página e inténtalo de nuevo.',
  invalid_request: 'La solicitud no tiene un formato válido. Revisa los datos e inténtalo de nuevo.',
  network_error: 'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
  not_found: 'No encontramos el recurso solicitado.',
  related_records: 'No se puede eliminar este evento porque tiene información relacionada.',
  validation_error: 'No pudimos guardar el evento. Revisa los datos e inténtalo de nuevo.',
}

/** Show a concise accessible message while a request is pending. */
export function LoadingMessage({ children = 'Cargando…' }) {
  return <p aria-live="polite" className="feedback feedback-loading">{children}</p>
}

/** Show the API's stable message and safe HTTP diagnostic fields. */
export function ErrorMessage({ error }) {
  if (!error) return null
  const message = ERROR_MESSAGES[error.code] || error.message || 'Ocurrió un problema. Inténtalo de nuevo.'
  const diagnostic = error.status
    ? `HTTP ${error.status} · ${error.code}`
    : error.code || null
  return (
    <div aria-live="assertive" className="feedback feedback-error" role="alert">
      <p>{message}</p>
      {diagnostic && <small>{diagnostic}</small>}
    </div>
  )
}

/** Show a neutral message when a successful request returns no records. */
export function EmptyMessage({ children }) {
  return <p className="feedback feedback-empty">{children}</p>
}
