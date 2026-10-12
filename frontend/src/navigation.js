/** Define the real application destinations shared by header and footer navigation. */

const PUBLIC_LINKS = [
  { label: 'Eventos', to: '/events', section: 'public' },
]

const ACCOUNT_LINKS = {
  authenticated: [{ label: 'Perfil', to: '/profile', section: 'account' }],
  visitor: [
    { label: 'Iniciar sesión', to: '/login', section: 'account' },
    { label: 'Registrarse', to: '/register', section: 'account' },
  ],
}

const ROLE_LINKS = {
  ATTENDEE: [
    { label: 'Mis inscripciones', to: '/my-registrations', section: 'personal' },
  ],
  ORGANIZER: [
    { label: 'Crear evento', to: '/events/new', section: 'events' },
    { label: 'Mis eventos', to: '/my-events', section: 'events' },
  ],
  ADMIN: [
    { label: 'Crear evento', to: '/events/new', section: 'events' },
    { label: 'Mis eventos', to: '/my-events', section: 'events' },
    { label: 'Panel administrativo', to: '/admin/dashboard', section: 'administration' },
    { label: 'Usuarios', to: '/admin/users', section: 'administration' },
  ],
}

const WORKSPACE_NAVIGATION = {
  ORGANIZER: [
    { heading: 'Espacio de trabajo', links: [
      { label: 'Resumen', to: '/profile', icon: '◫' },
      { label: 'Mis eventos', to: '/my-events', icon: '▦' },
      { label: 'Crear evento', to: '/events/new', icon: '+' },
    ] },
    { heading: 'Descubrimiento', links: [
      { label: 'Catálogo público', to: '/events', icon: '⌕' },
    ] },
  ],
  ADMIN: [
    { heading: 'Plataforma', links: [
      { label: 'Vista general', to: '/admin/dashboard', icon: '◫' },
      { label: 'Usuarios y roles', to: '/admin/users', icon: '♧' },
    ] },
    { heading: 'Eventos', links: [
      { label: 'Mis eventos', to: '/my-events', icon: '▦' },
      { label: 'Crear evento', to: '/events/new', icon: '+' },
      { label: 'Catálogo público', to: '/events', icon: '⌕' },
    ] },
    { heading: 'Cuenta', links: [
      { label: 'Perfil', to: '/profile', icon: '○' },
    ] },
  ],
}

/** Return role-appropriate links without treating presentation as authorization. */
export function getNavigation(auth) {
  const isAuthenticated = auth?.status === 'authenticated' && Boolean(auth.user)
  const roleLinks = isAuthenticated ? (ROLE_LINKS[auth.user.role] || []) : []
  const accountLinks = isAuthenticated
    ? ACCOUNT_LINKS.authenticated
    : ACCOUNT_LINKS.visitor

  return {
    primaryLinks: [...PUBLIC_LINKS, ...roleLinks],
    accountLinks,
  }
}

/** Return the verified workspace destinations for organizer or administrator areas. */
export function getWorkspaceNavigation(role) {
  return WORKSPACE_NAVIGATION[role] || []
}

/** Keep public pages in the public shell and management paths in their role workspace. */
export function getWorkspaceRole(auth, pathname) {
  if (auth?.status !== 'authenticated' || !auth.user) return null
  const { role } = auth.user
  const isAdminPath = pathname.startsWith('/admin/')
    || ['/profile', '/my-events', '/events/new'].includes(pathname)
    || /^\/events\/\d+$/.test(pathname)
  const isOrganizerPath = ['/profile', '/my-events', '/events/new'].includes(pathname)
    || /^\/events\/\d+$/.test(pathname)
  if (role === 'ADMIN' && isAdminPath) return role
  if (role === 'ORGANIZER' && isOrganizerPath) return role
  return null
}
