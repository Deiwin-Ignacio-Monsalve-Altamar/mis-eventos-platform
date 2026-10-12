/** Render the shared product footer outside standalone authentication pages. */

import { Link } from 'react-router-dom'
import { getNavigation } from '../navigation.js'

/** Provide real navigation destinations and the current copyright year. */
export default function SiteFooter({ auth }) {
  const currentYear = new Date().getFullYear()
  const { primaryLinks, accountLinks } = getNavigation(auth)

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
          {[...primaryLinks, ...accountLinks].map((item) => (
            <Link key={item.to} to={item.to}>
              {item.to === '/events' ? 'Explorar eventos' : item.to === '/profile' ? 'Mi perfil' : item.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="site-footer-legal">
        <span>© {currentYear} Mis Eventos</span>
        <span>Buenos planes, mejores historias.</span>
      </div>
    </footer>
  )
}
