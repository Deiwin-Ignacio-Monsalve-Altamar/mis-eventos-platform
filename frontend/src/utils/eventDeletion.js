/** Confirm a destructive event action before invoking its API operation. */

/** Request explicit confirmation and skip deletion when the user cancels. */
export async function confirmAndDeleteEvent({ eventTitle, confirmAction, deleteAction }) {
  const confirmed = confirmAction(
    `¿Eliminar el evento “${eventTitle}”? Esta acción no se puede deshacer. Si tiene sesiones o inscripciones, el servidor rechazará la eliminación.`,
  )
  if (!confirmed) return false
  await deleteAction()
  return true
}
