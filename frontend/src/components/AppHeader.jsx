/** Render the shared brand navigation and authentication-aware actions. */

import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import LogoutButton from './LogoutButton.jsx'
import { getNavigation } from '../navigation.js'

const ROLE_LABELS = {
  ADMIN: 'Administrador',
  ORGANIZER: 'Organizador',
  ATTENDEE: 'Asistente',
}

/** Show clear destinations while preserving the current authentication state. */
export default function AppHeader({ auth }) {
  const isAuthenticated = auth.status === 'authenticated' && Boolean(auth.user)
  const location = useLocation()
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const [navigationLocationKey, setNavigationLocationKey] = useState(null)
  const isNavigationOpen = navigationLocationKey === location.key
  const userMenuRef = useRef(null)
  const avatarButtonRef = useRef(null)
  const navigationButtonRef = useRef(null)
  const { primaryLinks, accountLinks } = getNavigation(auth)
  const navigationLinks = isAuthenticated ? primaryLinks : [...primaryLinks, ...accountLinks]

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

  useEffect(() => {
    if (!isNavigationOpen) return undefined

    function closeNavigationOnEscape(event) {
      if (event.key !== 'Escape') return
      setNavigationLocationKey(null)
      navigationButtonRef.current?.focus()
    }

    document.addEventListener('keydown', closeNavigationOnEscape)
    return () => document.removeEventListener('keydown', closeNavigationOnEscape)
  }, [isNavigationOpen])

  return (
    <header className="site-header">
      <Link aria-label="Mis Eventos, explorar eventos" className="brand" to="/events">
        <span aria-hidden="true" className="brand-mark">ME</span>
        <span>Mis Eventos</span>
      </Link>
      <button
        aria-controls="main-navigation"
        aria-expanded={isNavigationOpen}
        aria-label={isNavigationOpen ? 'Cerrar navegación' : 'Abrir navegación'}
        className="mobile-nav-toggle"
        onClick={() => setNavigationLocationKey(isNavigationOpen ? null : location.key)}
        ref={navigationButtonRef}
        type="button"
      >
        <span aria-hidden="true" className={isNavigationOpen ? 'mobile-nav-icon is-open' : 'mobile-nav-icon'} />
      </button>
      <nav
        aria-label="Navegación principal"
        className={`main-navigation${isNavigationOpen ? ' is-open' : ''}`}
        id="main-navigation"
      >
        {navigationLinks.map((item, index) => (
          <span className="main-navigation-item" key={item.to}>
            {index > 0 && navigationLinks[index - 1].section !== item.section && (
              <span aria-hidden="true" className="main-navigation-divider" />
            )}
            <NavLink
              className={({ isActive }) => [
                isActive ? 'active' : '',
                item.to === '/register' ? 'button button-primary header-signup-link' : '',
                item.to === '/login' ? 'header-login-link' : '',
              ].filter(Boolean).join(' ')}
              end={item.to === '/events'}
              onClick={() => setNavigationLocationKey(null)}
              to={item.to}
            >
              {item.label}
            </NavLink>
          </span>
        ))}
      </nav>
      {isAuthenticated && (
        <div className="header-actions">
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
                  <span className="user-session-status">Sesión activa</span>
                </div>
                {accountLinks.map((item) => (
                  <Link className="user-menu-item" key={item.to} onClick={() => setIsUserMenuOpen(false)} to={item.to}>{item.label}</Link>
                ))}
                <button aria-disabled="true" className="user-menu-item user-menu-disabled" disabled type="button">
                  <span>Ajustes</span><small>Próximamente</small>
                </button>
                <div className="user-menu-logout">
                  <LogoutButton />
                </div>
              </nav>
            )}
          </div>
        </div>
      )}
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
