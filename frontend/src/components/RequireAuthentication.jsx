/** Protect account routes with the application's existing cookie-auth state. */

import { Navigate, useLocation } from 'react-router-dom'
import { LoadingMessage } from './RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render a private page only after authentication has been confirmed. */
export default function RequireAuthentication({ children }) {
  const { state } = useAppState()
  const location = useLocation()

  if (state.auth.status === 'loading') {
    return <LoadingMessage>Estamos verificando tu sesión…</LoadingMessage>
  }
  if (state.auth.status !== 'authenticated') {
    return <Navigate replace state={{ from: `${location.pathname}${location.search}` }} to="/login" />
  }
  return children
}
