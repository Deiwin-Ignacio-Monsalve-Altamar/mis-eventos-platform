/** Show the current profile loaded from the authenticated API endpoint. */

import { Link } from 'react-router-dom'
import { ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Render the user's public profile or the appropriate authentication state. */
export default function ProfilePage() {
  const { state } = useAppState()
  const { auth } = state

  if (auth.status === 'loading') {
    return <LoadingMessage>Loading your profile…</LoadingMessage>
  }
  if (auth.status === 'error') {
    return (
      <section className="content-panel">
        <h1>Profile unavailable</h1>
        <ErrorMessage error={auth.error} />
      </section>
    )
  }
  if (auth.status !== 'authenticated') {
    return (
      <section className="content-panel">
        <p className="eyebrow">Your account</p>
        <h1>Sign in to view your profile</h1>
        <p>Your profile details are available after you sign in.</p>
        <div className="button-row">
          <Link className="button button-primary" to="/login">Sign in</Link>
          <Link className="button button-secondary" to="/register">Create an account</Link>
        </div>
      </section>
    )
  }

  return (
    <section className="content-panel profile-panel">
      <p className="eyebrow">Your account</p>
      <h1>Profile</h1>
      <dl className="event-facts">
        <div><dt>Name</dt><dd>{auth.user.first_name} {auth.user.last_name}</dd></div>
        <div><dt>Email</dt><dd>{auth.user.email}</dd></div>
      </dl>
    </section>
  )
}
