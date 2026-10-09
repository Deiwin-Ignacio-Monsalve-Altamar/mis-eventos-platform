/** Define the application shell and the public route table. */

import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider } from './state/AppState.jsx'
import useAppState from './state/useAppState.js'
import AppHeader from './components/AppHeader.jsx'
import CreateEventPage from './pages/CreateEventPage.jsx'
import EventDetailsPage from './pages/EventDetailsPage.jsx'
import EventListPage from './pages/EventListPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import SiteFooter from './components/SiteFooter.jsx'
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

  return (
    <div className={`app-shell${isAuthenticationPage ? ' app-shell-auth' : ''}`}>
      {!isAuthenticationPage && <AppHeader auth={auth} />}

      <main className="page-container">
        <Routes>
          <Route element={<EventListPage />} path="/" />
          <Route element={<EventListPage />} path="/events" />
          <Route element={<CreateEventPage />} path="/events/new" />
          <Route element={<EventDetailsPage />} path="/events/:eventId" />
          <Route element={<LoginPage />} path="/login" />
          <Route element={<RegisterPage />} path="/register" />
          <Route element={<ProfilePage />} path="/profile" />
          <Route element={<NotFoundPage />} path="*" />
        </Routes>
      </main>
      {!isAuthenticationPage && <SiteFooter auth={auth} />}
    </div>
  )
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
