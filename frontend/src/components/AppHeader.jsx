/** Render the shared brand navigation and authentication-aware actions. */

import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import LogoutButton from './LogoutButton.jsx'

const ROLE_LABELS = {
  ADMIN: 'Administrador',
  ORGANIZER: 'Organizador',
  ATTENDEE: 'Asistente',
}

/** Show clear destinations while preserving the current authentication state. */
export default function AppHeader({ auth }) {
  const isAuthenticated = auth.status === 'authenticated' && Boolean(auth.user)
  const { pathname } = useLocation()
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const userMenuRef = useRef(null)
  const avatarButtonRef = useRef(null)

  useEffect(() => {
    if (!isUserMenuOpen) return undefined

    function closeOnOutsideClick(event) {
      if (!userMenuRef.current?.contains(event.target)) setIsUserMenuOpen(false)
    }

    function closeOnEscape(event) {
      if (event.key !== 'Escape') return
      setIsUserMenuOpen(false)
      avatarButtonRef.current?.focus()
    }

    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [isUserMenuOpen])

  useEffect(() => {
    if (isUserMenuOpen) userMenuRef.current?.querySelector('a')?.focus()
  }, [isUserMenuOpen])

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
        {isAuthenticated && auth.user.role === 'ADMIN' && <NavLink to="/admin/users">Administración</NavLink>}
      </nav>
      <div className="header-actions">
        {isAuthenticated ? (
          <div className="user-menu" ref={userMenuRef}>
            <button
              aria-controls="user-navigation-menu"
              aria-expanded={isUserMenuOpen}
              aria-label="Abrir menú de usuario"
              className="user-avatar-button"
              onClick={() => setIsUserMenuOpen((open) => !open)}
              ref={avatarButtonRef}
              type="button"
            >
              <UserAvatar user={auth.user} />
            </button>
            {isUserMenuOpen && (
              <nav aria-label="Menú de usuario" className="user-menu-popover" id="user-navigation-menu">
                <div className="user-menu-identity">
                  <span>{auth.user.first_name} {auth.user.last_name}</span>
                  <span className={`user-role-badge user-role-${String(auth.user.role || '').toLowerCase()}`}>
                    {ROLE_LABELS[auth.user.role] || 'Usuario'} <small>{auth.user.role || ''}</small>
                  </span>
                </div>
                <Link className="user-menu-item" onClick={() => setIsUserMenuOpen(false)} to="/profile">Perfil</Link>
                {auth.user.role === 'ADMIN' && <Link className="user-menu-item" onClick={() => setIsUserMenuOpen(false)} to="/admin/users">Administrar usuarios</Link>}
                <button aria-disabled="true" className="user-menu-item user-menu-disabled" disabled type="button">
                  <span>Ajustes</span><small>Próximamente</small>
                </button>
                <div className="user-menu-logout">
                  <LogoutButton />
                </div>
              </nav>
            )}
          </div>
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

/** Render a deterministic geometric avatar derived from the user's public identity. */
function UserAvatar({ user }) {
  const identity = String(user.id ?? user.email ?? user.first_name ?? 'user')
  let seed = Array.from(identity).reduce((value, character) => (value * 31 + character.charCodeAt(0)) >>> 0, 7)
  const colors = ['#6D3BFF', '#D83B91', '#087F8C', '#B45309', '#3155A6']
  const background = colors[seed % colors.length]
  const shapes = Array.from({ length: 7 }, (_, index) => {
    const shapeSeed = (Math.imul(seed ^ (index + 1), 1664525) + 1013904223) >>> 0
    return {
      cx: 5 + (shapeSeed % 30),
      cy: 5 + ((shapeSeed >>> 5) % 30),
      radius: 3 + ((shapeSeed >>> 10) % 8),
      opacity: 0.25 + ((shapeSeed >>> 16) % 5) / 10,
      key: index,
    }
  })

  return (
    <svg aria-hidden="true" className="user-avatar-art" viewBox="0 0 40 40">
      <defs><clipPath id="user-avatar-clip"><circle cx="20" cy="20" r="20" /></clipPath></defs>
      <g clipPath="url(#user-avatar-clip)">
        <rect fill={background} height="40" width="40" />
        {shapes.map((shape) => <circle cx={shape.cx} cy={shape.cy} fill="#fff" key={shape.key} opacity={shape.opacity} r={shape.radius} />)}
      </g>
    </svg>
  )
}
