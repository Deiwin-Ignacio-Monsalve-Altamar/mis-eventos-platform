/** Provide distinct organizer and administrator workspaces around existing routes. */

import { useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import LogoutButton from './LogoutButton.jsx'
import { getWorkspaceNavigation } from '../navigation.js'

const ROLE_LABELS = { ADMIN: 'Administración global', ORGANIZER: 'Espacio de organización' }

/** Render role-specific navigation, a mobile drawer, and the existing route content. */
export default function WorkspaceLayout({ auth, role, children }) {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const location = useLocation()
  const navigation = getWorkspaceNavigation(role)
  const isAdmin = role === 'ADMIN'

  return (
    <div className={`workspace-shell workspace-${role.toLowerCase()}`}>
      {isNavigationOpen && <button aria-label="Cerrar menú de espacio de trabajo" className="workspace-scrim" onClick={() => setIsNavigationOpen(false)} type="button" />}
      <aside aria-label={`Navegación: ${ROLE_LABELS[role]}`} className={`workspace-sidebar${isNavigationOpen ? ' is-open' : ''}`} id="workspace-sidebar">
        <Link aria-label="Mis Eventos, ir al catálogo" className="workspace-brand" to="/events">
          <span aria-hidden="true" className="workspace-brand-mark">ME</span>
          <span>Mis Eventos<small>{isAdmin ? 'CONTROL CENTER' : 'EVENT STUDIO'}</small></span>
        </Link>
        <div className="workspace-label"><span className="workspace-role-dot" />{ROLE_LABELS[role]}</div>
        <nav aria-label="Navegación del espacio de trabajo" className="workspace-nav">
          {navigation.map((group) => (
            <section className="workspace-nav-group" key={group.heading}>
              <h2>{group.heading}</h2>
              {group.links.map((item) => (
                <NavLink
                  className={({ isActive }) => `workspace-nav-link${isActive ? ' active' : ''}`}
                  end={item.to === '/profile' || item.to === '/events' || item.to === '/my-events' || item.to === '/admin/dashboard' || item.to === '/admin/users' || item.to === '/events/new'}
                  key={item.to}
                  onClick={() => setIsNavigationOpen(false)}
                  to={item.to}
                >
                  <span aria-hidden="true" className="workspace-nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                  {location.pathname === item.to && <span aria-hidden="true" className="workspace-nav-current">•</span>}
                </NavLink>
              ))}
            </section>
          ))}
        </nav>
        <div className="workspace-account">
          <div aria-hidden="true" className="workspace-account-avatar">{`${auth.user.first_name?.[0] || ''}${auth.user.last_name?.[0] || ''}`.toUpperCase()}</div>
          <div className="workspace-account-copy">
            <strong>{auth.user.first_name} {auth.user.last_name}</strong>
            <span>{auth.user.email}</span>
            <small><i /> Sesión activa</small>
          </div>
          <LogoutButton />
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-topbar">
          <button
            aria-controls="workspace-sidebar"
            aria-expanded={isNavigationOpen}
            aria-label={isNavigationOpen ? 'Cerrar navegación' : 'Abrir navegación del espacio de trabajo'}
            className="workspace-menu-toggle"
            onClick={() => setIsNavigationOpen((open) => !open)}
            type="button"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <div className="workspace-topbar-context">
            <span>{isAdmin ? 'ADMIN WORKSPACE' : 'ORGANIZER WORKSPACE'}</span>
            <span aria-hidden="true">/</span>
            <strong>{ROLE_LABELS[role]}</strong>
          </div>
          <Link className="workspace-topbar-link" to="/events">Ver catálogo <span aria-hidden="true">↗</span></Link>
        </header>
        <main className="workspace-content">{children}</main>
      </div>
    </div>
  )
}
