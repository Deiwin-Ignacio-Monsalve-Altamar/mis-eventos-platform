/** Present the authenticated user's identity and role for role-specific profiles. */

const ROLE_LABELS = { ADMIN: 'Administrador', ORGANIZER: 'Organizador', ATTENDEE: 'Asistente' }

/** Render a consistent profile heading with a role-specific label. */
export default function ProfileHero({ user, eyebrow, description }) {
  const label = ROLE_LABELS[user.role] || 'Usuario'
  return (
    <header className={`profile-hero profile-hero-${String(user.role || '').toLowerCase()}`}>
      <div aria-hidden="true" className="profile-avatar">
        {`${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase()}
      </div>
      <div className="profile-identity">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{user.first_name} {user.last_name}</h1>
        <p>{user.email}</p>
        <span className="profile-role-label">{label} <small>{user.role}</small></span>
      </div>
      <p className="profile-welcome-note">{description}</p>
    </header>
  )
}
