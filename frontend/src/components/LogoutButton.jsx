/** Log out through shared authentication state and return to the public event list. */

import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ErrorMessage } from './RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render an accessible logout action that preserves authentication on failure. */
export default function LogoutButton() {
  const { signOut } = useAppState()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const requestInProgress = useRef(false)
  const pendingRedirect = useRef(null)

  useEffect(() => {
    if (pendingRedirect.current?.previousKey === location.key) return
    const resolveRedirect = pendingRedirect.current?.resolve
    if (resolveRedirect) {
      pendingRedirect.current = null
      resolveRedirect()
    }
  }, [location.key])

  function redirectToEvents() {
    return new Promise((resolve) => {
      pendingRedirect.current = { previousKey: location.key, resolve }
      navigate('/events', { replace: true })
    })
  }

  async function handleLogout() {
    if (requestInProgress.current) return
    requestInProgress.current = true
    setIsSubmitting(true)
    setError(null)
    try {
      await signOut(redirectToEvents)
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
