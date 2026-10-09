/** Define the application shell and the public route table. */

import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { AppProvider } from './state/AppState.jsx'
import useAppState from './state/useAppState.js'
import CreateEventPage from './pages/CreateEventPage.jsx'
import EventDetailsPage from './pages/EventDetailsPage.jsx'
import EventListPage from './pages/EventListPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
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

  return (
    <div className="app-shell">
      <header className="site-header">
        <NavLink className="brand" to="/events">
          Mis Eventos
        </NavLink>
        <nav aria-label="Main navigation" className="main-navigation">
          <NavLink to="/events">Events</NavLink>
          <NavLink to="/events/new">Create event</NavLink>
          <NavLink to="/profile">
            {auth.user ? 'Profile' : 'Sign in'}
          </NavLink>
        </nav>
      </header>

      <main className="page-container">
        <Routes>
          <Route element={<Navigate replace to="/events" />} path="/" />
          <Route element={<EventListPage />} path="/events" />
          <Route element={<CreateEventPage />} path="/events/new" />
          <Route element={<EventDetailsPage />} path="/events/:eventId" />
          <Route element={<LoginPage />} path="/login" />
          <Route element={<RegisterPage />} path="/register" />
          <Route element={<ProfilePage />} path="/profile" />
          <Route element={<NotFoundPage />} path="*" />
        </Routes>
      </main>
    </div>
  )
}

/** Explain when the requested location does not match a supported route. */
function NotFoundPage() {
  return (
    <section className="content-panel">
      <h1>Page not found</h1>
      <p>The requested page does not exist.</p>
      <NavLink to="/events">Browse events</NavLink>
    </section>
  )
}

export default App
