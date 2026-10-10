/** Render the shared brand navigation and authentication-aware actions. */

import { Link, NavLink, useLocation } from 'react-router-dom'

/** Show clear destinations while preserving the current authentication state. */
export default function AppHeader({ auth }) {
  const isAuthenticated = auth.status === 'authenticated' && Boolean(auth.user)
  const { pathname } = useLocation()

  return (
    <header className="site-header">
      <Link aria-label="Mis Eventos, explorar eventos" className="brand" to="/events">
        <span aria-hidden="true" className="brand-mark">ME</span>
        <span>Mis Eventos</span>
      </Link>
      <nav aria-label="Navegación principal" className="main-navigation">
        <NavLink className={pathname === '/' ? 'active' : undefined} end to="/events">Eventos</NavLink>
        <NavLink to="/events/new">Crear evento</NavLink>
        {isAuthenticated && <NavLink to="/my-events">Mis eventos</NavLink>}
      </nav>
      <div className="header-actions">
        {isAuthenticated ? (
          <Link className="header-profile-link" to="/profile">Mi perfil</Link>
        ) : (
          <>
            <Link className="header-login-link" to="/login">Iniciar sesión</Link>
            <Link className="button button-primary header-signup-link" to="/register">Únete gratis</Link>
          </>
        )}
      </div>
    </header>
  )
}
