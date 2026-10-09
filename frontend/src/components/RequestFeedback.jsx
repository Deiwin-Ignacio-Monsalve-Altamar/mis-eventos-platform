/** Render consistent loading, error, and empty-state feedback for pages. */

/** Show a concise accessible message while a request is pending. */
export function LoadingMessage({ children = 'Loading…' }) {
  return <p aria-live="polite" className="feedback feedback-loading">{children}</p>
}

/** Show the API's stable message and safe HTTP diagnostic fields. */
export function ErrorMessage({ error }) {
  if (!error) return null
  const diagnostic = error.status
    ? `HTTP ${error.status} · ${error.code}`
    : error.code || null
  return (
    <div aria-live="assertive" className="feedback feedback-error" role="alert">
      <p>{error.message}</p>
      {diagnostic && <small>{diagnostic}</small>}
    </div>
  )
}

/** Show a neutral message when a successful request returns no records. */
export function EmptyMessage({ children }) {
  return <p className="feedback feedback-empty">{children}</p>
}
