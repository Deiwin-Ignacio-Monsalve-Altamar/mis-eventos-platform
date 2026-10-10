/** Synchronize event editor navigation with its query-string state. */

/** Add or remove only the edit flag while preserving other query parameters. */
export function getEventEditorLocation(pathname, search, isOpen) {
  const parameters = new URLSearchParams(search)
  if (isOpen) parameters.set('edit', '1')
  else parameters.delete('edit')
  const query = parameters.toString()
  return `${pathname}${query ? `?${query}` : ''}`
}
