/** Render the shared product footer outside standalone authentication pages. */

import { Link } from 'react-router-dom'

/** Provide real navigation destinations and the current copyright year. */
export default function SiteFooter({ auth }) {
  const isAuthenticated = auth.status === 'authenticated' && Boolean(auth.user)
  const currentYear = new Date().getFullYear()

  return (
    <footer className="site-footer">
      <div className="site-footer-main">
        <div className="site-footer-brand-block">
          <Link aria-label="Mis Eventos, explorar eventos" className="brand footer-brand" to="/events">
            <span aria-hidden="true" className="brand-mark">ME</span>
            <span>Mis Eventos</span>
          </Link>
          <p>Encuentra tu próximo plan. Haz que pase.</p>
        </div>
        <nav aria-label="Enlaces del pie de página" className="footer-navigation">
          <Link to="/events">Explorar eventos</Link>
          <Link to="/events/new">Crear evento</Link>
          {isAuthenticated ? (
            <Link to="/profile">Mi perfil</Link>
          ) : (
            <>
              <Link to="/login">Iniciar sesión</Link>
              <Link to="/register">Registrarse</Link>
            </>
          )}
        </nav>
      </div>
      <div className="site-footer-legal">
        <span>© {currentYear} Mis Eventos</span>
        <span>Buenos planes, mejores historias.</span>
      </div>
    </footer>
  )
}
