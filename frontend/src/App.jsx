/** Define the application shell and the public route table. */

import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider } from './state/AppState.jsx'
import useAppState from './state/useAppState.js'
import AppHeader from './components/AppHeader.jsx'
import WorkspaceLayout from './components/WorkspaceLayout.jsx'
import AuthLayout from './components/AuthLayout.jsx'
import CreateEventPage from './pages/CreateEventPage.jsx'
import EventDetailsPage from './pages/EventDetailsPage.jsx'
import EventListPage from './pages/EventListPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import AdminProfile from './pages/AdminProfile.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import MyEventsPage from './pages/MyEventsPage.jsx'
import MyRegistrationsPage from './pages/MyRegistrationsPage.jsx'
import SiteFooter from './components/SiteFooter.jsx'
import RequireAuthentication from './components/RequireAuthentication.jsx'
import RequireRole from './components/RequireRole.jsx'
import AdminUsersPage from './pages/AdminUsersPage.jsx'
import { LoadingMessage } from './components/RequestFeedback.jsx'
import { getWorkspaceRole } from './navigation.js'
import './App.css'

/** Render the application provider, shell, and page routes. */
function App() {
  return (
    <AppProvider>
      <ApplicationRoutes />
    </AppProvider>
  )
}

/** Render navigation and all supported application destinations. */
function ApplicationRoutes() {
  const { state } = useAppState()
  const { auth } = state
  const { pathname } = useLocation()
  const isAuthenticationPage = pathname === '/login' || pathname === '/register'
  const isEntryRoute = pathname === '/'
  const workspaceRole = getWorkspaceRole(auth, pathname)
  const routes = (
    <Routes>
      <Route element={<RoleHome auth={auth} />} path="/" />
      <Route element={<EventListPage />} path="/events" />
      <Route element={<CreateEventPage />} path="/events/new" />
      <Route element={<EventDetailsPage />} path="/events/:eventId" />
      <Route element={<LoginPage />} path="/login" />
      <Route element={<RegisterPage />} path="/register" />
      <Route element={<RequireAuthentication><ProfilePage /></RequireAuthentication>} path="/profile" />
      <Route element={<RequireAuthentication><MyEventsPage /></RequireAuthentication>} path="/my-events" />
      <Route element={<RequireAuthentication><MyRegistrationsPage /></RequireAuthentication>} path="/my-registrations" />
      <Route element={<RequireAuthentication><RequireRole role="ADMIN"><AdminProfile user={auth.user} /></RequireRole></RequireAuthentication>} path="/admin/dashboard" />
      <Route element={<RequireAuthentication><RequireRole role="ADMIN"><AdminUsersPage /></RequireRole></RequireAuthentication>} path="/admin/users" />
      <Route element={<NotFoundPage />} path="*" />
    </Routes>
  )

  return (
    <div className={`app-shell${isAuthenticationPage || isEntryRoute ? ' app-shell-auth' : ''}`}>
      {!isAuthenticationPage && !isEntryRoute && !workspaceRole && <AppHeader auth={auth} />}
      {workspaceRole
        ? <WorkspaceLayout auth={auth} role={workspaceRole}>{routes}</WorkspaceLayout>
        : <main className="page-container">{routes}</main>}
      {!isAuthenticationPage && !isEntryRoute && !workspaceRole && <SiteFooter auth={auth} />}
    </div>
  )
}

/** Use the root route as a role-aware entry point without redirecting while auth loads. */
function RoleHome({ auth }) {
  if (auth.status === 'loading') {
    return (
      <AuthLayout>
        <section aria-label="Verificación de sesión" className="auth-panel">
          <LoadingMessage>Estamos verificando tu sesión…</LoadingMessage>
        </section>
      </AuthLayout>
    )
  }

  const destinations = {
    ATTENDEE: '/events',
    ORGANIZER: '/my-events',
    ADMIN: '/admin/dashboard',
  }
  const destination = auth.user?.role ? destinations[auth.user.role] : null

  if (auth.status !== 'authenticated' || !destination) {
    return <LoginPage defaultDestination="/" />
  }
  return <Navigate replace to={destination} />
}

/** Explain when the requested location does not match a supported route. */
function NotFoundPage() {
  return (
    <section className="content-panel">
      <h1>Página no encontrada</h1>
      <p>La página solicitada no existe.</p>
      <Link to="/events">Explorar eventos</Link>
    </section>
  )
}

export default App
