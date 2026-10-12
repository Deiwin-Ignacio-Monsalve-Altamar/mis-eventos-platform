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
