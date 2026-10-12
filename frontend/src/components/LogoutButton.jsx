/** Log out through shared authentication state and return to the appropriate entry page. */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorMessage } from './RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render an accessible logout action that preserves authentication on failure. */
export default function LogoutButton() {
  const { state, signOut } = useAppState()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const requestInProgress = useRef(false)
  function redirectAfterLogout() {
    const destination = ['ORGANIZER', 'ADMIN'].includes(state.auth.user?.role) ? '/login' : '/events'
    navigate(destination, { replace: true })
  }

  async function handleLogout() {
    if (requestInProgress.current) return
    requestInProgress.current = true
    setIsSubmitting(true)
    setError(null)
    try {
      await signOut(redirectAfterLogout)
    } catch (requestError) {
      setError(requestError)
    } finally {
      requestInProgress.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <div className="logout-action">
      {error && <ErrorMessage error={error} />}
      <button aria-busy={isSubmitting} className="user-menu-item user-menu-logout-button" disabled={isSubmitting} onClick={handleLogout} type="button">
        <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
          <path d="M10 17l5-5-5-5M15 12H3" />
          <path d="M12 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5" />
        </svg>
        {isSubmitting ? 'Cerrando sesión…' : 'Cerrar sesión'}
      </button>
    </div>
  )
}
