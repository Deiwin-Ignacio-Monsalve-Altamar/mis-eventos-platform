/** Present event and session editors in an accessible, viewport-bounded dialog. */

import { useEffect, useId, useRef } from 'react'
import EventArtwork from './EventArtwork.jsx'

/** Keep editor actions available while the dialog body scrolls independently. */
export default function EditorModal({ title, artworkTitle, onClose, children }) {
  const dialogRef = useRef(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => {
      if (dialog?.open) dialog.close()
    }
  }, [])

  function handleCancel(event) {
    event.preventDefault()
    onClose()
  }

  function handleBackdropClick(event) {
    if (event.target === dialogRef.current) onClose()
  }

  return (
    <dialog
      aria-labelledby={titleId}
      aria-modal="true"
      className="editor-modal"
      onCancel={handleCancel}
      onClick={handleBackdropClick}
      ref={dialogRef}
      role="dialog"
    >
      <header className="editor-modal-header">
        <EventArtwork title={artworkTitle} variant="thumbnail" />
        <div className="editor-modal-heading">
          <p className="eyebrow">Mis Eventos</p>
          <h2 id={titleId}>{title}</h2>
        </div>
        <button
          aria-label="Cerrar ventana de edición"
          className="editor-modal-close"
          onClick={onClose}
          type="button"
        >
          <span aria-hidden="true">×</span>
        </button>
      </header>
      <div className="editor-modal-content">{children}</div>
    </dialog>
  )
}
