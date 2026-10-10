/** Check event administration against both session and backend ownership. */

/** Grant controls only after the owner-only endpoint confirms access. */
export function canManageEvent(auth, ownerAccess) {
  return auth.status === 'authenticated' && ownerAccess === 'owner'
}
