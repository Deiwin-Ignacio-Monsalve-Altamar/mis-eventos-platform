/** Restrict a route to an authenticated user with the required role. */

import { Link } from 'react-router-dom'
import useAppState from '../state/useAppState.js'

/** Render a clear forbidden state when the authenticated role is insufficient. */
export default function RequireRole({ role, children }) {
  const { state } = useAppState()

  if (state.auth.user?.role !== role) {
    return (
      <section className="content-panel admin-access-denied">
        <h1>Acceso restringido</h1>
        <p>No tienes permiso para consultar esta sección.</p>
        <Link className="button button-secondary" to="/events">Volver a eventos</Link>
      </section>
    )
  }
  return children
}
