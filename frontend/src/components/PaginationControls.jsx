/** Render accessible previous and next controls for API-backed result pages. */

/** Present real pagination metadata and disable controls at page boundaries. */
export default function PaginationControls({ pagination, onPageChange, disabled = false }) {
  if (!pagination || pagination.total_pages < 2) return null

  return (
    <nav aria-label="Paginación de eventos" className="pagination-controls">
      <button
        className="button button-secondary"
        disabled={disabled || pagination.page <= 1}
        onClick={() => onPageChange(pagination.page - 1)}
        type="button"
      >Anterior</button>
      <p aria-live="polite">
        Página <strong>{pagination.page}</strong> de <strong>{pagination.total_pages}</strong>
        <span> · {pagination.total} {pagination.total === 1 ? 'evento' : 'eventos'}</span>
      </p>
      <button
        className="button button-secondary"
        disabled={disabled || pagination.page >= pagination.total_pages}
        onClick={() => onPageChange(pagination.page + 1)}
        type="button"
      >Siguiente</button>
    </nav>
  )
}
