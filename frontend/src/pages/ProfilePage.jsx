/** Select a profile experience from the backend-authenticated role. */

import { Link } from 'react-router-dom'
import AuthErrorMessage from '../components/AuthErrorMessage.jsx'
import { LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'
import AdminProfile from './AdminProfile.jsx'
import AttendeeProfile from './AttendeeProfile.jsx'
import OrganizerProfile from './OrganizerProfile.jsx'

/** Render the role-specific profile after shared authentication has resolved. */
export default function ProfilePage() {
  const { state } = useAppState()
  const { auth } = state

  if (auth.status === 'loading') return <LoadingMessage>Estamos cargando tu perfil…</LoadingMessage>
  if (auth.status === 'error') {
    return <section className="content-panel profile-recovery"><p className="eyebrow">Tu cuenta</p><h1>Tu perfil no está disponible</h1><AuthErrorMessage error={auth.error} /><Link className="button button-secondary" to="/login">Volver a iniciar sesión</Link></section>
  }
  if (auth.status !== 'authenticated') {
    return <section className="content-panel profile-recovery"><p className="eyebrow">Tu cuenta</p><h1>Inicia sesión para ver tu perfil</h1><p>Cuando inicies sesión podrás consultar la información de tu cuenta.</p><div className="button-row"><Link className="button button-primary" to="/login">Iniciar sesión</Link><Link className="button button-secondary" to="/register">Crear una cuenta</Link></div></section>
  }

  if (auth.user.role === 'ADMIN') return <AdminProfile user={auth.user} />
  if (auth.user.role === 'ORGANIZER') return <OrganizerProfile user={auth.user} />
  return <AttendeeProfile user={auth.user} />
}
